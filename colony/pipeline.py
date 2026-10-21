"""Restartable, bounded research/implementation and publication pipeline."""

import json
import os
from pathlib import Path
from collections import Counter
import time
import uuid

from .autonomy_store import BudgetExceeded, DuplicateAttempt
from .github_broker import GitHubBroker, PublicationRejected, SRE_FILES, checks_state, safe_slug, validate_public_text
from .model_policy import choose_model
from .operations import OPS_SCHEMA, enqueue_followups, parse_operations_output, render_operations_report
from .worker import execute_job


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

    def _update(self, cycle, phase=None, **data):
        return self.autonomy.update_cycle(cycle["id"], phase=phase, **data)

    def _event(self, cycle, kind, message, **data):
        self.tasks.record_event(kind, "controller", message, cycle.get("task_id"), data)

    def _job(self, cycle, stage, prompt, timeout, sandbox, schema=None):
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
        except Exception:
            self.autonomy.finish_attempt(attempt, time.monotonic() - started, status="failed")
            raise
        self.autonomy.finish_attempt(attempt, float(result.get("elapsed_seconds", time.monotonic() - started)),
                                     usage=result.get("usage", {}),
                                     status="completed" if result.get("status") == "completed" else "failed")
        return result

    def _heartbeat(self, cycle):
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
        if revision >= int(self.policy.get("max_revisions", 2)):
            return self._terminal(cycle, "needs_review", "Revision limit reached: " + feedback[:1500])
        task = self.tasks.get_task(cycle["task_id"])
        if task and task["status"] in {"review", "failed"}:
            self.tasks.transition(task["id"], "ready", "controller", summary="Bounded revision requested")
        self._event(cycle, "cycle.revision", "Scheduling a bounded revision", revision=revision + 1)
        return self._update(cycle, "authoring", revision=revision + 1, feedback=feedback,
                            reviewed_sha=None, review=None, review_attempt=0, author_completed=False)

    def advance(self, cycle):
        """Advance one durable stage. Repeated publication/merge calls reconcile GitHub."""
        task = self.tasks.get_task(cycle["task_id"])
        if task is None:
            return self._terminal(cycle, "failed", "Cycle task no longer exists")
        try:
            phase = cycle["phase"]
            if phase == "queued":
                context = self.broker.prepare_worktree(cycle)
                if task["role"] == "sre":
                    context.update(governance_required=True, governance_status="candidate")
                return self._update(cycle, "authoring", revision=0, **context)
            if phase == "authoring":
                return self._author(cycle, task)
            if phase == "publishing":
                if not self.policy.get("automatic_publication", False):
                    return self._terminal(cycle, "needs_review", "Automatic publication is disabled")
                sha = self.broker.commit(cycle, task)
                cycle = self._update(cycle, head_sha=sha)
                pr = self.broker.publish(cycle, task, cycle.get("summary", "Candidate ready for independent review"))
                self.tasks.set_task_artifacts(task["id"], branch=cycle["branch"], pr_url=pr["url"])
                self._event(cycle, "pr.published", "Candidate published for review", pr_url=pr["url"], head_sha=sha)
                return self._update(cycle, "reviewing", pr_number=pr["number"], pr_url=pr["url"])
            if phase == "reviewing":
                return self._review(cycle, task)
            if phase == "review_publication":
                return self._publish_review(cycle)
            if phase in {"ci", "merging"}:
                return self._ci(cycle, task)
            return cycle
        except BudgetExceeded:
            raise
        except DuplicateAttempt:
            return self._terminal(cycle, "needs_review", "A completed or interrupted stage cannot run twice")
        except PublicationRejected as exc:
            return self._terminal(cycle, "needs_review", str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            return self._terminal(cycle, "needs_review", "Invalid candidate/review data: " + type(exc).__name__)

    def _author(self, cycle, task):
        self._require_budget(int(self.policy.get("author_timeout_seconds", 600)))
        agent_id = "colony-author-" + cycle["id"][:10]
        self.tasks.register_agent(agent_id, "Colony author", task["role"])
        lease = int(self.policy.get("author_timeout_seconds", 600)) + 120
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
                           int(self.policy.get("author_timeout_seconds", 600)),
                           "workspace-write" if implementation else "read-only",
                           OPS_SCHEMA if task["role"] == "operations" else None)
        if result.get("status") != "completed":
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
        result = self._job(cycle, "review:%s:%s" % (cycle["head_sha"], cycle.get("review_attempt", 0)), prompt,
                           int(self.policy.get("review_timeout_seconds", 240)), "read-only", REVIEW_SCHEMA)
        if result.get("status") != "completed":
            attempt = int(cycle.get("review_attempt", 0))
            if attempt < int(self.policy.get("max_revisions", 2)):
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

    def plan(self):
        """Generate bounded new work from repository evidence when the queue empties."""
        dispatched = {item["task_id"] for item in self.autonomy.list_cycles()}
        if any(item["status"] in {"ready", "running"} and item["id"] not in dispatched
               for item in self.tasks.snapshot()["tasks"]):
            return {"status": "waiting", "tasks": []}
        self._require_budget(int(self.policy.get("planner_timeout_seconds", 180)))
        cycle = self.autonomy.create_cycle("PLAN-" + uuid.uuid4().hex[:12], "planner")
        context = self.broker.prepare_worktree(cycle)
        cycle = self._update(cycle, "planning", revision=0, **context)
        recent = [{"id": item["id"], "title": item["title"], "status": item["status"]}
                  for item in self.tasks.snapshot()["tasks"][-30:]]
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
Recent tasks: %s
""" % (", ".join(sorted(SRE_FILES)), json.dumps(recent))
        result = self._job(cycle, "planner:0", prompt,
                           int(self.policy.get("planner_timeout_seconds", 180)), "read-only", PLAN_SCHEMA)
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
