"""Restartable, bounded research/implementation and publication pipeline."""

import json
import os
from pathlib import Path
from collections import Counter
import time
import threading
import uuid

from .autonomy_store import BudgetExceeded, CapacityUnavailable, DuplicateAttempt
from .github_broker import GitHubBroker, PublicationRejected, SRE_FILES, checks_state, safe_slug, validate_public_text
from .model_policy import choose_model
from .network import AuthenticationFailure, NetworkUnavailable, classify_model_failure, probe_model_connectivity
from .network_recovery import retry_delay, schedule_retry
from .operations import OPS_SCHEMA, enqueue_followups, parse_operations_output, render_operations_report
from .recovery import TRIAGE_SCHEMA, apply_triage_result
from .worker import WorkerProcessUncertain, execute_job


REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["verdict", "summary", "findings"],
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "changes_requested", "reject"]},
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
}
PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["tasks"],
    "properties": {"tasks": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
        "type": "object", "additionalProperties": False,
        "required": ["title", "role", "description", "acceptance"],
        "properties": {
            "title": {"type": "string"}, "role": {"type": "string", "enum": ["engineer", "researcher", "sre"]},
            "description": {"type": "string"},
            "acceptance": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string"}},
        },
    }}},
}


class Pipeline:
    def __init__(self, root, task_store, autonomy, policy, broker=None, executor=None):
        self.root_alias = str(Path(root).absolute())
        self.root = Path(root).resolve()
        self.tasks, self.autonomy, self.policy = task_store, autonomy, dict(policy)
        self.broker = broker or GitHubBroker(root, policy)
        self.executor = executor or execute_job
        self._model_context = threading.local()
        self._provider_lock = threading.RLock()

    def _update(self, cycle, phase=None, **data):
        return self.autonomy.update_cycle(cycle["id"], phase=phase, **data)

    def _event(self, cycle, kind, message, **data):
        self.tasks.record_event(kind, "controller", message, cycle.get("task_id"), data)

    def _provider_failed(self, cycle):
        with self._provider_lock:
            self._record_provider_failure(cycle)

    def _record_provider_failure(self, cycle):
        current = self.autonomy.get_cycle(cycle["id"])
        count = int(current.get("provider_network_retry_count", 0)) + 1
        delay = retry_delay(count, self.policy.get("network_backoff_base_seconds", 5),
                            self.policy.get("network_backoff_max_seconds", 900))
        self._update(current, provider_network_offline=True, provider_network_retry_count=count,
                     provider_next_retry_at=time.time() + delay)

    def _ensure_provider_available(self):
        # A probe that started before another lane observed a fresh outage
        # must not clear that newer failure with a stale successful result.
        with self._provider_lock:
            self._check_provider_available()

    def _check_provider_available(self):
        # Persist the provider outage on the originating cycle, so all stages
        # and restarts share the guard without a separate mutable policy file.
        offline = [item for item in self.autonomy.list_cycles() if item.get("provider_network_offline")]
        if not offline:
            return
        if time.time() < max(item.get("provider_next_retry_at", 0) for item in offline):
            raise NetworkUnavailable("Model provider retry backoff is active")
        try:
            probe_model_connectivity()
        except NetworkUnavailable:
            for item in offline:
                self._provider_failed(item)
            raise
        for item in offline:
            self._update(item, provider_network_offline=False, provider_next_retry_at=None)

    def _job(self, cycle, stage, prompt, timeout, sandbox, schema=None):
        self._ensure_provider_available()
        if stage.startswith("author:"):
            stage += ":net%s" % int(cycle.get("author_network_retry_count", 0))
        elif stage.startswith("review:"):
            stage += ":net%s" % int(cycle.get("review_network_retry_count", 0))
        elif stage.startswith("planner:"):
            stage += ":net%s" % int(cycle.get("planner_network_retry_count", 0))
        elif stage.startswith("triage:"):
            stage += ":net%s" % int(cycle.get("triage_network_retry_count", 0))
        attempt = self.autonomy.reserve_attempt(cycle["id"], stage, timeout, self.policy)
        revision = int(cycle.get("review_attempt", 0)) if stage.startswith("review:") else int(cycle.get("revision", 0))
        selection = choose_model(self.policy, cycle["role"], stage.split(":")[0], revision=revision,
                                 trust_critical=stage.startswith("review:") and cycle["role"] in {"engineer", "sre"})
        self._update(cycle, model=selection["model"], reasoning_effort=selection["reasoning_effort"],
                     model_reason=selection["reason"])
        self._event(cycle, "model.selected", selection["reason"], stage=stage, **selection)
        policy = dict(self.policy, model=selection["model"], reasoning_effort=selection["reasoning_effort"],
                      role="reviewer" if stage.startswith("review:") else cycle["role"],
                      model_reason=selection["reason"], _database=str(self.tasks.path))
        started = time.monotonic()
        try:
            result = self.executor(self.root, Path(cycle["worktree"]), prompt, timeout, sandbox,
                                   "colony-%s-%s" % (stage.split(":")[0], cycle["id"][:10]),
                                   task_id=cycle["task_id"] if stage.startswith("author:") else None,
                                   output_schema=schema,
                                   heartbeat=lambda: self._heartbeat(cycle), policy=policy)
        except WorkerProcessUncertain:
            self.autonomy.finish_attempt(attempt, time.monotonic() - started, status="interrupted")
            return {"status": "uncertain", "summary": "Worker process outcome requires operator reconciliation"}
        except Exception as error:
            self.autonomy.finish_attempt(attempt, time.monotonic() - started, status="failed")
            failure = error if isinstance(error, (NetworkUnavailable, AuthenticationFailure)) else classify_model_failure(error)
            if failure:
                if isinstance(failure, NetworkUnavailable):
                    self._provider_failed(cycle)
                field = ("author_network_retry_count" if stage.startswith("author:") else
                         "review_network_retry_count" if stage.startswith("review:") else
                         "planner_network_retry_count" if stage.startswith("planner:") else
                         "triage_network_retry_count" if stage.startswith("triage:") else None)
                if field:
                    self._update(cycle, **{field: int(cycle.get(field, 0)) + 1})
                raise failure from error
            raise
        uncertain = result.get("status") in {"interrupted", "uncertain", "running"}
        self.autonomy.finish_attempt(attempt, float(result.get("elapsed_seconds", time.monotonic() - started)),
                                     usage=result.get("usage", {}),
                                     status="interrupted" if uncertain else
                                     "completed" if result.get("status") == "completed" else "failed")
        # Uncertain process identity takes precedence over a network-looking
        # summary. Retain the complete reservation and require reconciliation.
        if uncertain:
            return result
        if result.get("status") != "completed":
            failure = classify_model_failure(result.get("summary"))
            if failure:
                if isinstance(failure, NetworkUnavailable):
                    self._provider_failed(cycle)
                field = ("author_network_retry_count" if stage.startswith("author:") else
                         "review_network_retry_count" if stage.startswith("review:") else
                         "planner_network_retry_count" if stage.startswith("planner:") else
                         "triage_network_retry_count" if stage.startswith("triage:") else None)
                if field:
                    self._update(cycle, **{field: int(cycle.get(field, 0)) + 1})
                raise failure
        return result

    def probe_connectivity(self):
        probe = getattr(self.broker, "probe_connectivity", None)
        return True if probe is None else probe()

    def _heartbeat(self, cycle):
        # Parallel workers report their task leases, while only the main
        # supervisor owns aggregate service status and active-cycle reporting.
        if not getattr(self._model_context, "deferred", False):
            self.autonomy.set_service("working", pid=os.getpid(), active_cycle=cycle["id"], message="Executing bounded model task")
        task = self.tasks.get_task(cycle["task_id"])
        if task and task["status"] == "running":
            self.tasks.heartbeat(task["id"], task["lease_owner"], lease_seconds=300)

    def _output(self, result, cycle):
        path = result.get("output_path") or result.get("result_path")
        if path and Path(path).is_file():
            with Path(path).open(encoding="utf-8") as stream:
                value = stream.read(32001)
        else:
            value = result.get("summary", "")
        if not isinstance(value, str) or not value.strip() or len(value) > 32000:
            raise PublicationRejected("Worker output is absent or exceeds its limit")
        for local, label in ((str(cycle.get("worktree", "")), "<checkout>"),
                             (str(self.root), "<repository>"), (self.root_alias, "<repository>"),
                             (str(Path.home()), "<home>")):
            if local:
                value = value.replace(local, label)
        return value.strip()

    def _require_budget(self, timeout):
        budget = self.autonomy.get_budget(self.policy)
        if budget["remaining_attempts"] < 1 or budget["remaining_seconds"] < timeout:
            raise BudgetExceeded("Daily model budget cannot reserve %s seconds; resets %s" % (timeout, budget["resets_at"]))

    def _operations_context(self):
        snapshot = self.tasks.snapshot()
        cycles = self.autonomy.list_cycles()
        context = {
            "role_charters": {
                "engineer": "Implement local Lean procedures and examples within the fixed engineering allowlist.",
                "researcher": "Produce complete scoped research artifacts with falsifiable experiments and honest evidence.",
                "sre": "Implement narrow controller reliability proposals as separate governance PRs; no automatic deployment or merge.",
                "operations": "Audit bottlenecks and missing roles in read-only mode; propose bounded work and role charters without granting permissions.",
                "reviewer": "Independently review the exact candidate head in a separate read-only model context.",
                "planner": "Propose a bounded backlog within existing roles and publication scopes.",
            },
            "task_status_counts": dict(Counter(item["status"] for item in snapshot["tasks"])),
            "task_role_counts": dict(Counter(item["role"] for item in snapshot["tasks"])),
            "cycle_phase_counts": dict(Counter(item["phase"] for item in cycles)),
            "tasks": [{key: item[key] for key in ("id", "title", "role", "status")}
                      for item in snapshot["tasks"][:40]],
            "recent_cycles": [{key: item[key] for key in ("task_id", "role", "phase", "revision", "ci_status") if key in item}
                              for item in cycles[-20:]],
        }
        return validate_public_text(json.dumps(context, ensure_ascii=False))

    def _terminal(self, cycle, phase, message):
        task = self.tasks.get_task(cycle["task_id"])
        if task and task["status"] not in {"done", "failed", "blocked"}:
            actor = task["lease_owner"] if task["status"] == "running" else "controller"
            self.tasks.transition(task["id"], "blocked" if phase in {"needs_review", "blocked"} else "failed",
                                  actor, summary=message)
        self._event(cycle, "cycle." + phase, message)
        return self._update(cycle, phase, last_error=message)

    def _revise(self, cycle, feedback):
        revision = int(cycle.get("revision", 0))
        limit = 0 if cycle.get("recovery_kind") == "repair" else int(self.policy.get("max_revisions", 2))
        if revision >= limit:
            return self._terminal(cycle, "needs_review", "Revision limit reached: " + feedback[:1500])
        task = self.tasks.get_task(cycle["task_id"])
        if task and task["status"] in {"review", "failed"}:
            self.tasks.transition(task["id"], "ready", "controller", summary="Bounded revision requested")
        self._event(cycle, "cycle.revision", "Scheduling a bounded revision", revision=revision + 1)
        return self._update(cycle, "authoring", revision=revision + 1, feedback=feedback,
                            reviewed_sha=None, review=None, review_attempt=0, author_completed=False)

    def prepare_model_cycle(self, cycle):
        """Controller-thread preparation before submitting one model stage."""
        if cycle.get("role") == "planner":
            return self.prepare_plan(cycle=cycle) or cycle
        if cycle.get("recovery_kind") == "triage" and not cycle.get("worktree"):
            try:
                return self._update(cycle, **self.broker.prepare_worktree(cycle))
            except NetworkUnavailable:
                current = self.autonomy.get_cycle(cycle["id"])
                return schedule_retry(current, self._update,
                                      base_seconds=self.policy.get("network_backoff_base_seconds", 5),
                                      max_seconds=self.policy.get("network_backoff_max_seconds", 900))
            except (AuthenticationFailure, PublicationRejected) as exc:
                return self._terminal(cycle, "needs_review", str(exc))
        return cycle

    def advance_model(self, cycle):
        """Run one prepared model stage, leaving all publication to the controller.

        Worktrees and shared Git preparation must already have completed on the
        supervisor thread. Thread-local deferral keeps legacy synchronous calls
        intact without changing policy or allowing one worker to publish.
        """
        if cycle.get("phase") not in {"authoring", "reviewing", "triaging", "planning"}:
            raise ValueError("Only a prepared model stage can run in a model lane")
        if not cycle.get("worktree"):
            raise ValueError("Model lane requires a controller-prepared worktree")
        previous = getattr(self._model_context, "deferred", False)
        self._model_context.deferred = True
        try:
            return self.advance(cycle)
        finally:
            self._model_context.deferred = previous

    def advance(self, cycle):
        """Advance one durable stage. Repeated publication/merge calls reconcile GitHub."""
        if cycle.get("role") == "planner" and cycle.get("phase") in {"queued", "planning"}:
            return self.plan(cycle=cycle)
        if cycle.get("recovery_kind") == "triage":
            return self._triage(cycle)
        task = self.tasks.get_task(cycle["task_id"])
        if task is None:
            return self._terminal(cycle, "failed", "Cycle task no longer exists")
        if cycle.get("recovery_kind") == "repair":
            root = self.autonomy.get_cycle(cycle["recovery_root_id"])
            source_task = self.tasks.get_task(root["task_id"])
            if (root.get("recovery_status") in {"escalated", "controller_scope_review", "resolved"}
                    or source_task is None or source_task["status"] not in {"blocked", "failed", "review"}
                    or source_task["description"] != cycle.get("source_task_description")
                    or source_task["acceptance"] != cycle.get("source_task_acceptance")):
                return self._terminal(cycle, "needs_review", "Source ownership or original specification changed during repair")
        try:
            phase = cycle["phase"]
            if phase == "queued":
                if cycle.get("recovery_kind") == "repair":
                    root = self.autonomy.get_cycle(cycle["recovery_root_id"])
                    source = self.broker.get_pr(root["pr_number"])
                    if (source.get("state") != "OPEN" or source.get("headRefOid") != cycle.get("source_head_sha")
                            or source.get("url") != cycle.get("source_pr_url")):
                        return self._terminal(cycle, "needs_review", "Source PR changed before the bounded repair began")
                context = self.broker.prepare_worktree(cycle)
                if task["role"] == "sre":
                    context.update(governance_required=True, governance_status="candidate")
                return self._update(cycle, "authoring", revision=0, **context)
            if phase == "authoring":
                return self._author(cycle, task)
            if phase == "planning" and cycle.get("role") == "planner":
                return self.plan(cycle=cycle)
            if phase == "publishing":
                if not self.policy.get("automatic_publication", False):
                    return self._terminal(cycle, "needs_review", "Automatic publication is disabled")
                sha = self.broker.commit(cycle, task)
                publication = {"head_sha": sha}
                if cycle.get("publish_candidate_sha") != sha:
                    publication.update(publish_candidate_sha=sha,
                        publish_previous_head_sha=cycle.get("published_head_sha") or
                        (cycle.get("head_sha") if cycle.get("pr_number") else None))
                cycle = self._update(cycle, **publication)
                pr = self.broker.publish(cycle, task, cycle.get("summary", "Candidate ready for independent review"))
                self.tasks.set_task_artifacts(task["id"], branch=cycle["branch"], pr_url=pr["url"])
                self._event(cycle, "pr.published", "Candidate published for review", pr_url=pr["url"], head_sha=sha)
                return self._update(cycle, "reviewing", pr_number=pr["number"], pr_url=pr["url"], published_head_sha=sha)
            if phase == "reviewing":
                return self._review(cycle, task)
            if phase == "review_publication":
                return self._publish_review(cycle)
            if phase in {"ci", "merging"}:
                return self._ci(cycle, task)
            return cycle
        except (BudgetExceeded, CapacityUnavailable):
            raise
        except NetworkUnavailable:
            current = self.autonomy.get_cycle(cycle["id"])
            return schedule_retry(current, self._update,
                                  base_seconds=self.policy.get("network_backoff_base_seconds", 5),
                                  max_seconds=self.policy.get("network_backoff_max_seconds", 900))
        except AuthenticationFailure as exc:
            return self._terminal(cycle, "needs_review", "Remote authentication requires operator attention: " + str(exc))
        except DuplicateAttempt:
            return self._terminal(cycle, "needs_review", "A completed or interrupted stage cannot run twice")
        except PublicationRejected as exc:
            return self._terminal(cycle, "needs_review", str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            return self._terminal(cycle, "needs_review", "Invalid candidate/review data: " + type(exc).__name__)

    def _triage(self, cycle):
        """One operational diagnosis may assign a repair, never authorize a merge."""
        root = self.autonomy.get_cycle(cycle["recovery_root_id"])
        if root.get("recovery_status") in {"escalated", "controller_scope_review", "resolved", "awaiting_controller_integration"}:
            return self._update(cycle, "done", triage_action="cancelled")
        timeout = min(180, int(self.policy.get("planner_timeout_seconds", 180)))
        if cycle.get("phase") != "triage_handoff":
            self._require_budget(timeout)
        try:
            if cycle.get("phase") == "triage_handoff":
                remote = self.broker.get_pr(root["pr_number"])
                if (remote.get("state") != "OPEN" or remote.get("headRefOid") != cycle.get("source_head_sha")
                        or remote.get("url") != cycle.get("source_pr_url")):
                    raise PublicationRejected("Source PR changed before the recovery handoff")
                apply_triage_result(self.tasks, self.autonomy, self.policy, cycle, cycle["triage_result"])
                return self.autonomy.get_cycle(cycle["id"])
            if not cycle.get("worktree"):
                cycle = self._update(cycle, **self.broker.prepare_worktree(cycle))
            original = self.tasks.get_task(root["task_id"])
            remote = self.broker.get_pr(root["pr_number"])
            if (remote.get("state") != "OPEN" or remote.get("headRefOid") != cycle.get("source_head_sha")
                    or remote.get("url") != cycle.get("source_pr_url")):
                raise PublicationRejected("Source PR changed or closed; controller reconciliation required")
            def public_excerpt(value):
                try:
                    return validate_public_text(str(value or ""))[:3000]
                except PublicationRejected:
                    return "Operational details redacted; inspect the public source PR and review."

            evidence = {"task_id": root["task_id"], "title": original["title"],
                        "description": cycle["source_task_description"],
                        "acceptance": cycle["source_task_acceptance"], "role": cycle["source_task_role"],
                        "pr_url": cycle["source_pr_url"], "head_sha": cycle["source_head_sha"],
                        "last_error": public_excerpt(root.get("last_error")),
                        "prior_feedback": public_excerpt(root.get("feedback")),
                        "review": public_excerpt(json.dumps(root.get("review"))), "revision": root.get("revision")}
            prompt = ("You are the READ ONLY blocker triage worker. Read AGENTS.md and relevant public source. "
                      "Diagnose exactly this parked PR and choose repair or escalate. A repair is one fresh "
                      "author call (480 seconds maximum) and one independent review (240 seconds maximum), "
                      "all charged to the existing daily ledger. Supply one narrow repair_title and "
                      "repair_description; role must equal the original execution role. The controller copies "
                      "the original description and acceptance verbatim; you cannot replace or weaken them. "
                      "The new repair starts from current main, so it must reproduce any useful source-PR "
                      "implementation needed for the FULL original acceptance, using the public source head. "
                      "Do not turn an implementation into a research proposal. Escalate if current scopes "
                      "cannot satisfy that acceptance, authority must change, or a bounded fix is infeasible. "
                      "No edits, execution of candidate code, publication, merge, deployment, credentials, "
                      "new permissions, or agents. Return only the strict JSON, under 8000 characters. "
                      "Escalation strings may be empty except diagnosis.\nEvidence:\n" +
                      validate_public_text(json.dumps(evidence, ensure_ascii=False)))
            self.autonomy.update_cycle(root["id"], recovery_status="triaging",
                                       recovery_next_action="Diagnose the parked PR and assign one bounded repair")
            result = self._job(cycle, "triage:0", prompt, timeout, "read-only", TRIAGE_SCHEMA)
            if result.get("status") != "completed":
                return self._terminal(cycle, "needs_review", "Bounded blocker triage failed; controller escalation required")
            payload = json.loads(self._output(result, cycle))
            cycle = self._update(cycle, "triage_handoff", triage_result=payload)
            if getattr(self._model_context, "deferred", False):
                return cycle
            return self._triage(cycle)
        except (BudgetExceeded, CapacityUnavailable):
            raise
        except NetworkUnavailable:
            current = self.autonomy.get_cycle(cycle["id"])
            return schedule_retry(current, self._update,
                                  base_seconds=self.policy.get("network_backoff_base_seconds", 5),
                                  max_seconds=self.policy.get("network_backoff_max_seconds", 900))
        except Exception as error:
            # No second diagnosis for an uncertain or malformed stage.
            return self._terminal(cycle, "needs_review", "Blocker triage stopped: " + type(error).__name__)

    def reconcile_recovery(self, root_cycle_id):
        """Close a superseded source only after its full replacement is integrated."""
        root = self.autonomy.get_cycle(root_cycle_id)
        if root.get("recovery_status") != "repair_merged":
            return root
        if time.time() < root.get("recovery_reconcile_after", 0):
            return root
        try:
            triage = self.autonomy.get_cycle(root["recovery_triage_cycle_id"])
            repair = self.autonomy.get_cycle(root["recovery_repair_cycle_id"])
            source = self.tasks.get_task(root["task_id"])
            task = self.tasks.get_task(root["recovery_repair_task_id"])
            recovered_summary = "Original acceptance satisfied by reviewed replacement " + str(task.get("pr_url") or "")
            if (source["status"] not in {"blocked", "failed", "review"}
                    and not (source["status"] == "done" and source["summary"] == recovered_summary)):
                raise PublicationRejected("Source task is active, ready, or completed by another action")
            if (repair.get("recovery_root_id") != root["id"] or repair.get("recovery_kind") != "repair"
                    or source["description"] != triage["source_task_description"]
                    or source["acceptance"] != triage["source_task_acceptance"]
                    or source["pr_url"] != triage["source_pr_url"] or root["pr_url"] != triage["source_pr_url"]
                    or task["acceptance"] != triage["source_task_acceptance"]
                    or task["role"] != triage["source_task_role"] or source["role"] != task["role"]
                    or not task["description"].startswith(triage["source_task_description"])
                    or repair.get("phase") != "done" or task["status"] != "done"
                    or repair.get("review", {}).get("verdict") != "approve"
                    or not repair.get("reviewed_sha") or repair["reviewed_sha"] != repair.get("head_sha")
                    or repair.get("ci_status") != "passed"):
                raise PublicationRejected("Replacement lacks unchanged original acceptance and review evidence")
            remote = self.broker.get_pr(repair["pr_number"])
            if (remote.get("state") != "MERGED" or not remote.get("mergedAt")
                    or remote.get("headRefOid") != repair["reviewed_sha"]
                    or remote.get("url") != task["pr_url"]
                    or checks_state(remote, self.policy.get("required_checks", ["control-plane", "lean-seed"])) != "passed"):
                raise PublicationRejected("Replacement merge, head, or required CI was not confirmed")
            source_remote = self.broker.get_pr(root["pr_number"])
            if source_remote.get("url") != triage["source_pr_url"]:
                raise PublicationRejected("Source PR identity differs from the captured recovery target")
            self.broker.close_superseded_pr(root["pr_number"], triage["source_head_sha"], task["pr_url"], root["id"])
            self.tasks.complete_recovery(source["id"], task["id"], triage["source_task_description"],
                                         triage["source_task_acceptance"], task["pr_url"])
            resolved = self.autonomy.update_cycle(root["id"], recovery_status="resolved", recovery_owner="controller",
                source_pr_url=triage["source_pr_url"], source_head_sha=triage["source_head_sha"],
                recovery_replacement_pr_url=task["pr_url"], recovery_replacement_head_sha=repair["reviewed_sha"],
                recovery_next_action="Resolved; source PR closed as superseded after verified replacement merge")
            self._event(root, "recovery.resolved", "Original acceptance satisfied by a verified merged replacement",
                        replacement_task_id=task["id"], replacement_pr_url=task["pr_url"])
            return resolved
        except PublicationRejected as error:
            return self.autonomy.update_cycle(root["id"], recovery_status="escalated", recovery_owner="controller",
                recovery_reason=str(error), recovery_next_action="Inspect replacement evidence and reconcile the source PR")
        except Exception:
            attempts = int(root.get("recovery_reconcile_attempts", 0)) + 1
            return self.autonomy.update_cycle(root["id"], recovery_reconcile_attempts=attempts,
                recovery_reconcile_after=time.time() + 300,
                recovery_status="escalated" if attempts >= 3 else "repair_merged", recovery_owner="controller",
                recovery_next_action="Reconcile remote closure and integrated acceptance; no model work is repeated")

    def _author(self, cycle, task):
        self._ensure_provider_available()
        timeout = int(self.policy.get("author_timeout_seconds", 600))
        if cycle.get("recovery_kind") == "repair":
            timeout = min(480, timeout)
        self._require_budget(timeout)
        agent_id = "colony-author-" + cycle["id"][:10]
        self.tasks.register_agent(agent_id, "Colony author", task["role"])
        lease = timeout + 120
        self.tasks.recover_expired()
        current = self.tasks.get_task(task["id"])
        if current["status"] == "ready":
            current = self.tasks.claim(agent_id, task_id=task["id"], lease_seconds=lease)
        if not current or current["status"] != "running" or current["lease_owner"] != agent_id:
            return self._terminal(cycle, "needs_review", "Author could not obtain its exact task lease")
        implementation = task["role"] in {"engineer", "sre"}
        if task["role"] == "operations":
            mode = ("You are the READ ONLY operations steward. Audit actual swarm work, recurring failures, "
                    "queue bottlenecks, missing roles, and whether existing role charters fit the mission. "
                    "Do not edit code or configuration. Return the specified structured operations report, "
                    "up to five proposed role charters as plain strings, and up to three follow-up tasks using "
                    "only engineer, researcher, or sre. Role charters are proposals and grant no authority. "
                    "Execution or permission changes require a separate SRE governance PR and controller integration. "
                    "Follow-up tasks are considered only after this report's exact-head independent review, "
                    "required CI, and public PR merge. Distinguish measured facts from hypotheses. "
                    "Keep the total structured JSON under 20000 characters; keep fields and tool-output excerpts concise. "
                    "Inspect relevant public source and research artifacts. Controller metrics and current role charters:\n" +
                    self._operations_context())
        elif task["role"] == "sre":
            mode = ("You are an SRE implementation worker preparing a separate governance PR. "
                    "You may edit ONLY these exact paths, plus research/: " + ", ".join(sorted(SRE_FILES)) + ". "
                    "Implement and test the scoped reliability fix. After independent review and required CI, "
                    "this candidate awaits separate controller integration. The pinned deployment is not changed "
                    "by this worker. Do not edit service.py, __main__.py, colony.json, AGENTS.md, workflows, "
                    "model policy, evaluators, challenge statements, or benchmarks. "
                    "Do not read or modify secrets or host configuration.")
        elif implementation:
            mode = ("You may edit ONLY lean/Colony/Tactic.lean, lean/Colony.lean, lean/Colony/Procedures/, "
                    "lean/Colony/Examples/, and research/. Run relevant Lean checks if time permits. "
                    "Do not read or modify secrets or host configuration.")
        else:
            mode = ("This task is READ ONLY. Return a complete, narrowly scoped research artifact in your final answer. "
                    "Distinguish plans, experiments, and measured results; do not assert proposed work is implemented.")
        prompt = """You are a bounded QED Colony implementation/research worker. Read AGENTS.md.
Task {id}: {title}
{description}
Acceptance criteria: {criteria}
Base revision: {base}
Prior review/CI feedback: {feedback}

{mode}
Do not commit, push, open PRs, contact others, merge, deploy, spawn agents, change
credentials, install global dependencies, or change policy/CI/evaluation/challenges.
Do not claim performance or proof assurance without evidence. Preserve original
theorems, definitions, assumptions and bounds. Never introduce sorry/admit/axioms.
No machine-local paths, credentials, or private logs in the final response.
Return a concise complete result with actual checks and remaining limitations.
""".format(id=task["id"], title=task["title"], description=task.get("description", ""),
           criteria=json.dumps(task.get("acceptance", [])), base=cycle["base_sha"],
           feedback=cycle.get("feedback", "None"), mode=mode)
        result = self._job(cycle, "author:%s" % cycle.get("revision", 0), prompt,
                           timeout,
                           "workspace-write" if implementation else "read-only",
                           OPS_SCHEMA if task["role"] == "operations" else None)
        if result.get("status") != "completed":
            if result.get("status") in {"interrupted", "uncertain", "running"}:
                return self._terminal(cycle, "needs_review", "Author process outcome is uncertain; operator reconciliation required")
            self.tasks.transition(task["id"], "failed", agent_id, summary="Bounded author attempt failed")
            return self._revise(cycle, "Author attempt failed: " + str(result.get("summary", "unknown failure"))[:1500])
        output = validate_public_text(self._output(result, cycle))
        if task["role"] == "operations":
            payload = parse_operations_output(output)
            output = validate_public_text(render_operations_report(payload))
            cycle = self._update(cycle, operations_report=payload)
        if not implementation:
            path = Path(cycle["worktree"]) / "research" / "colony" / (safe_slug(task["id"]) + ".md")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# %s\n\nTask `%s`; base revision `%s`.\n\n%s\n" %
                            (task["title"], task["id"], cycle["base_sha"], output), encoding="utf-8")
        self.broker.validate_changes(cycle["worktree"], task["role"], cycle["base_sha"])
        self.tasks.transition(task["id"], "review", agent_id, summary=output[:3000], branch=cycle["branch"])
        return self._update(cycle, "publishing", summary=output[:12000], author_completed=True)

    def _review(self, cycle, task):
        pr = self.broker.get_pr(cycle["pr_number"])
        if pr.get("mergedAt") or pr.get("state") == "MERGED":
            return self._terminal(cycle, "needs_review", "PR was merged before the controller recorded its review")
        if pr.get("state") != "OPEN" or pr.get("headRefOid") != cycle.get("head_sha"):
            return self._terminal(cycle, "needs_review", "PR changed outside the bounded publication pipeline")
        prompt = """You are the independent QED Colony reviewer in a NEW READ ONLY model context.
Read AGENTS.md. Review git diff {base}..HEAD and relevant source files.
Task {id}: {title}
Description: {description}
Acceptance: {acceptance}
Exact candidate head: {head}
Review correctness, preserved original theorem/specifications, no forbidden
axioms/unchecked proof claims, actual evidence, scope, and remaining limitations.
A research proposal must not claim implementation or fabricated measurements.
Do not edit files, run candidate code, push, publish, spawn agents, or contact others.
Return structured JSON. Approve only if acceptance is satisfied; otherwise give
specific actionable findings. A successful author process is not evidence of proof.
""".format(base=cycle["base_sha"], id=task["id"], title=task["title"], description=task.get("description", ""),
           acceptance=json.dumps(task.get("acceptance", [])), head=cycle["head_sha"])
        if task["role"] == "operations":
            prompt += ("\nThis is an operations report. Review its proposed follow-up tasks as executable queue "
                       "proposals: they must stay within existing engineer/researcher/sre scopes. Proposed role "
                       "charters grant no permissions. Any controller execution or authority change needs a "
                       "separate SRE governance PR and controller integration. Approve only the actual public report.\n")
        timeout = int(self.policy.get("review_timeout_seconds", 240))
        if cycle.get("recovery_kind") == "repair":
            timeout = min(240, timeout)
        result = self._job(cycle, "review:%s:%s" % (cycle["head_sha"], cycle.get("review_attempt", 0)), prompt,
                           timeout, "read-only", REVIEW_SCHEMA)
        if result.get("status") != "completed":
            if result.get("status") in {"interrupted", "uncertain", "running"}:
                return self._terminal(cycle, "needs_review", "Reviewer process outcome is uncertain; operator reconciliation required")
            attempt = int(cycle.get("review_attempt", 0))
            limit = 0 if cycle.get("recovery_kind") == "repair" else int(self.policy.get("max_revisions", 2))
            if attempt < limit:
                self._event(cycle, "review.retry", "Review failed; retrying with a stronger configured model", attempt=attempt + 1)
                return self._update(cycle, "reviewing", review_attempt=attempt + 1)
            return self._terminal(cycle, "needs_review", "Independent review exhausted its bounded retries; candidate is not approved")
        review = json.loads(self._output(result, cycle))
        if (not isinstance(review, dict) or set(review) != {"verdict", "summary", "findings"}
                or review.get("verdict") not in {"approve", "changes_requested", "reject"}
                or not isinstance(review.get("summary"), str) or len(review["summary"]) > 12000
                or not isinstance(review.get("findings"), list) or len(review["findings"]) > 30
                or any(not isinstance(item, str) or len(item) > 3000 for item in review["findings"])):
            raise PublicationRejected("Reviewer returned an invalid review object")
        validate_public_text(json.dumps(review))
        # Save the review before its network publication. Restart can repost idempotently.
        cycle = self._update(cycle, "review_publication", review=review, reviewed_sha=cycle["head_sha"])
        if getattr(self._model_context, "deferred", False):
            return cycle
        return self._publish_review(cycle)

    def _publish_review(self, cycle):
        review = cycle["review"]
        self.broker.comment_review(cycle["pr_number"], review, cycle["reviewed_sha"], cycle["id"])
        self.tasks.record_review(dict(review, actor="colony-reviewer", task_id=cycle["task_id"],
                                      head_sha=cycle["reviewed_sha"], pr_url=cycle["pr_url"]))
        if review["verdict"] == "changes_requested":
            return self._revise(cycle, review["summary"] + "\n" + "\n".join(review["findings"]))
        if review["verdict"] == "reject":
            return self._terminal(cycle, "needs_review", "Independent reviewer rejected the candidate: " + review["summary"][:1500])
        return self._update(cycle, "ci")

    def _ci(self, cycle, task):
        pr = self.broker.get_pr(cycle["pr_number"])
        checks = [{key: value for key, value in check.items() if key in
                   {"name", "context", "status", "conclusion", "state", "detailsUrl", "targetUrl"}}
                  for check in (pr.get("statusCheckRollup") or [])]
        cycle = self._update(cycle, checks=checks, ci_checks=checks)
        if pr.get("mergedAt") or pr.get("state") == "MERGED":
            if (cycle.get("review", {}).get("verdict") != "approve"
                    or not cycle.get("reviewed_sha") or pr.get("headRefOid") != cycle["reviewed_sha"]
                    or (cycle.get("ci_status") != "passed" and checks_state(pr, self.policy.get(
                        "required_checks", ["control-plane", "lean-seed"])) != "passed")):
                return self._terminal(cycle, "needs_review", "External merge lacks the controller's exact-head review and CI evidence")
            if task["role"] == "operations":
                payload = parse_operations_output(cycle.get("operations_report"))
                follow_up_ids = enqueue_followups(self.tasks, cycle, payload, self.policy)
                cycle = self._update(cycle, follow_up_task_ids=follow_up_ids)
            self.tasks.transition(task["id"], "done", "controller", summary="Reviewed candidate merged with successful required CI",
                                  branch=cycle["branch"], pr_url=cycle["pr_url"])
            self._event(cycle, "pr.merged", "Reviewed candidate merged", pr_url=cycle["pr_url"], head_sha=cycle.get("reviewed_sha"))
            return self._update(cycle, "done", merged_at=pr.get("mergedAt"))
        if pr.get("state") != "OPEN" or pr.get("headRefOid") != cycle.get("reviewed_sha"):
            return self._terminal(cycle, "needs_review", "PR is closed or its head differs from the reviewed commit")
        if cycle.get("review", {}).get("verdict") != "approve":
            return self._terminal(cycle, "needs_review", "Candidate lacks an approving independent review")
        state = checks_state(pr, self.policy.get("required_checks", ["control-plane", "lean-seed"]))
        if state == "failed":
            return self._revise(cycle, "Required GitHub CI failed for head %s. Fix the cause; "
                                "never modify protected CI/evaluation files.\n%s" %
                                (cycle["reviewed_sha"], self.broker.failure_details(pr)))
        if state != "passed":
            return self._update(cycle, "ci", ci_status="pending")
        if task["role"] == "sre":
            self._event(cycle, "governance.ready", "Reviewed SRE governance PR passed CI and awaits controller integration",
                        pr_url=cycle["pr_url"], head_sha=cycle["reviewed_sha"])
            return self._update(cycle, "needs_review", governance_required=True,
                                governance_status="awaiting_controller_integration", ci_status="passed", last_error=None)
        if not self.policy.get("automatic_merge", False):
            return self._terminal(cycle, "needs_review", "Review and CI passed; automatic merge is disabled")
        if pr.get("mergeable") == "CONFLICTING":
            return self._terminal(cycle, "needs_review", "Candidate conflicts with the current base branch")
        if pr.get("mergeable") != "MERGEABLE" or pr.get("mergeStateStatus") not in {"CLEAN", "HAS_HOOKS"}:
            return self._update(cycle, "ci", ci_status="waiting_for_mergeability")
        cycle = self._update(cycle, "merging", ci_status="passed")
        merged = self.broker.merge(cycle["pr_number"], cycle["reviewed_sha"])
        if merged.get("mergedAt") or merged.get("state") == "MERGED":
            return self._ci(cycle, task)
        return cycle

    def prepare_plan(self, cycle=None):
        """Create/reuse one planner worktree on the serialized controller thread."""
        dispatched = {item["task_id"] for item in self.autonomy.list_cycles()}
        if any(item["status"] in {"ready", "running"} and item["id"] not in dispatched
               for item in self.tasks.snapshot()["tasks"]):
            return None
        if cycle is None:
            cycle = next((item for item in self.autonomy.list_cycles()
                          if item["role"] == "planner" and item["phase"] in {"queued", "planning", "waiting_network"}), None)
        if cycle is not None and cycle["phase"] == "waiting_network":
            return cycle
        self._require_budget(int(self.policy.get("planner_timeout_seconds", 180)))
        if cycle is None:
            cycle = self.autonomy.create_cycle("PLAN-" + uuid.uuid4().hex[:12], "planner")
        try:
            context = {} if cycle.get("worktree") else self.broker.prepare_worktree(cycle)
        except NetworkUnavailable:
            current = self.autonomy.get_cycle(cycle["id"])
            return schedule_retry(current, self._update,
                                  base_seconds=self.policy.get("network_backoff_base_seconds", 5),
                                  max_seconds=self.policy.get("network_backoff_max_seconds", 900))
        except AuthenticationFailure as exc:
            return self._update(cycle, "needs_review", last_error=str(exc))
        return self._update(cycle, "planning", revision=0, **context)

    def plan(self, cycle=None):
        """Synchronous compatibility wrapper; parallel lanes run prepared plans."""
        if not getattr(self._model_context, "deferred", False):
            cycle = self.prepare_plan(cycle=cycle)
        if cycle is None:
            return {"status": "waiting", "tasks": []}
        if cycle["phase"] != "planning":
            return {"status": cycle["phase"], "tasks": []}
        return self._plan_model(cycle)

    def _plan_model(self, cycle):
        """Infer and validate bounded tasks without preparing or publishing Git."""
        snapshot = self.tasks.snapshot()["tasks"]
        recent = [{"id": item["id"], "title": item["title"], "status": item["status"]}
                  for item in snapshot[-30:]]
        active = [{key: item[key] for key in ("id", "title", "role", "status")}
                  for item in snapshot if item["status"] not in {"done", "failed"}]
        prompt = """You are QED Colony's READ ONLY research planner. Read AGENTS.md, docs/roadmap.md,
lean/Colony/Tactic.lean, research experiments, and current task history below.
Propose 1 to 3 small independent tasks that materially advance the local Lean
tactic toward complex program verification. Favor a narrow engineering experiment
with a falsifiable check. Architecture is open. Do not repeat completed work or
lower theorem/specification/assurance requirements. Engineer edits are restricted
to lean/Colony/Tactic.lean, lean/Colony.lean, lean/Colony/Procedures/,
lean/Colony/Examples/, research/. Policy, CI, evaluator, benchmark and challenge
changes require separate governance review and cannot be automated here.
For a narrowly scoped controller reliability fix, use role sre. Its exact editable
paths are: %s, plus research/. SRE proposals are separate governance PRs requiring
independent review and CI before a controller-integration handoff; they never
automatically merge or deploy. Do not create tasks changing other protected files.
Read-only operations audits are scheduled separately by the periodic operations
scheduler or controller, which enforces a single pending audit. Do not create
operations tasks from this empty-queue planner.
Tasks must fit one bounded model attempt, contain precise acceptance criteria,
and require no user action or other tasks. Research tasks produce complete public
artifacts; do not call implementation a research artifact. No edits, publication,
spawning agents or contact. Return the specified JSON schema.
Do not duplicate any active, ready, running, or review objective listed below.
For parallel independence prefer separate modules/files. Each task description
must name its intended files or artifact and any shared integration surface;
do not propose work that depends on another active task completing first.
Recent tasks: %s
Active unfinished tasks (including parked work): %s
""" % (", ".join(sorted(SRE_FILES)), json.dumps(recent), json.dumps(active))
        try:
            result = self._job(cycle, "planner:0", prompt,
                               int(self.policy.get("planner_timeout_seconds", 180)), "read-only", PLAN_SCHEMA)
        except NetworkUnavailable:
            current = self.autonomy.get_cycle(cycle["id"])
            schedule_retry(current, self._update,
                           base_seconds=self.policy.get("network_backoff_base_seconds", 5),
                           max_seconds=self.policy.get("network_backoff_max_seconds", 900))
            return {"status": "waiting_network", "tasks": []}
        except AuthenticationFailure as exc:
            self._update(cycle, "needs_review", last_error=str(exc))
            return {"status": "needs_review", "tasks": []}
        if result.get("status") in {"interrupted", "uncertain", "running"}:
            self._update(cycle, "needs_review", last_error="Planner process outcome is uncertain; operator reconciliation required")
            return {"status": "needs_review", "tasks": []}
        if result.get("status") != "completed":
            self._update(cycle, "failed", last_error="Bounded planner attempt failed")
            return {"status": "failed", "tasks": []}
        payload = json.loads(self._output(result, cycle))
        tasks = payload.get("tasks") if isinstance(payload, dict) else None
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 3:
            raise PublicationRejected("Planner returned an invalid task count")
        prepared = []
        for item in tasks:
            if (not isinstance(item, dict) or set(item) != {"title", "role", "description", "acceptance"}
                    or item["role"] not in {"engineer", "researcher", "sre"}
                    or not isinstance(item["title"], str) or not 5 <= len(item["title"]) <= 180
                    or not isinstance(item["description"], str) or not 20 <= len(item["description"]) <= 6000
                    or not isinstance(item["acceptance"], list) or not 1 <= len(item["acceptance"]) <= 6
                    or any(not isinstance(value, str) or not 5 <= len(value) <= 1000 for value in item["acceptance"])):
                raise PublicationRejected("Planner returned an invalid scoped task")
            validate_public_text(json.dumps(item))
            prepared.append(dict(item, id="AUTO-" + uuid.uuid4().hex[:10], priority=50, depends_on=[], status="ready"))
        self.tasks.seed(prepared)
        self._event(cycle, "planner.completed", "Planner added bounded scoped work", task_ids=[item["id"] for item in prepared])
        self._update(cycle, "done", planned_task_ids=[item["id"] for item in prepared])
        return {"status": "planned", "tasks": prepared}
