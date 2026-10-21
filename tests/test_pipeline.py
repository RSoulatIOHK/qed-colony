import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from colony.autonomy_store import AutonomyStore, BudgetExceeded
from colony.pipeline import PLAN_SCHEMA, Pipeline
from colony.github_broker import PublicationRejected
from colony.network import NetworkUnavailable
from colony.operations import OPS_SCHEMA
from colony.store import Store


def good_pr(sha):
    return {"number": 7, "url": "https://github.com/example/repo/pull/7", "state": "OPEN",
            "headRefOid": sha, "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
                                  for name in ["control-plane", "lean-seed"]]}


class FakeBroker:
    def __init__(self, root):
        self.root, self.pr, self.commits = root, None, 0
        self.publications, self.reviews, self.merges = [], [], []

    def prepare_worktree(self, cycle):
        worktree = self.root / "checkout"
        worktree.mkdir(exist_ok=True)
        return {"worktree": str(worktree), "branch": "codex/test", "base_sha": "b" * 40}

    def validate_changes(self, *args):
        return ["lean/Colony/Tactic.lean"]

    def commit(self, cycle, task):
        self.commits += 1
        return str(self.commits) * 40

    def publish(self, cycle, task, summary):
        self.publications.append(cycle["head_sha"])
        self.pr = good_pr(cycle["head_sha"])
        return self.pr

    def get_pr(self, number):
        return self.pr

    def comment_review(self, *args):
        self.reviews.append(args)

    def merge(self, number, sha):
        self.merges.append(sha)
        self.pr.update(state="MERGED", mergedAt="2026-01-01T00:00:00Z")
        return self.pr

    def failure_details(self, pr):
        return "lean-seed: FAILURE\nerror: unknown identifier example"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.provider_probe = patch("colony.pipeline.probe_model_connectivity", return_value=True).start()
        self.addCleanup(patch.stopall)
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = Store(self.root / "db.sqlite").initialize()
        self.auto = AutonomyStore(self.store.path).initialize()
        self.store.seed([{"id": "T1", "title": "A scoped implementation", "role": "engineer",
                          "description": "Improve one generic procedure.", "acceptance": ["Kernel checked result"]}])
        self.policy = {"max_daily_seconds": 1000, "max_daily_attempts": 20,
                       "author_timeout_seconds": 10, "review_timeout_seconds": 10,
                       "planner_timeout_seconds": 10, "automatic_publication": True,
                       "automatic_merge": True, "max_revisions": 2}
        self.broker = FakeBroker(self.root)
        self.jobs = []
        self.review = {"verdict": "approve", "summary": "Acceptance verified", "findings": []}
        self.pipeline = Pipeline(self.root, self.store, self.auto, self.policy,
                                 broker=self.broker, executor=self.executor)
        self.cycle = self.auto.create_cycle("T1", "engineer")

    def tearDown(self):
        self.directory.cleanup()

    def executor(self, root, worktree, prompt, timeout, sandbox, agent_id, **kwargs):
        self.jobs.append({"prompt": prompt, "sandbox": sandbox, "agent_id": agent_id, **kwargs})
        summary = json.dumps(self.review) if kwargs.get("output_schema") else "Implemented generic proof step; local check passed."
        return {"status": "completed", "summary": summary, "usage": {"input_tokens": 20}, "elapsed_seconds": 1}

    def step(self):
        self.cycle = self.pipeline.advance(self.auto.get_cycle(self.cycle["id"]))
        return self.cycle

    def to_ci(self):
        for _ in range(4):
            self.step()
        self.assertEqual(self.cycle["phase"], "ci")

    def test_full_cycle_claims_reviews_and_merges_exact_head(self):
        self.to_ci()
        self.step()
        self.assertEqual(self.cycle["phase"], "done")
        self.assertEqual(self.store.get_task("T1")["status"], "done")
        self.assertEqual(self.broker.merges, [self.cycle["reviewed_sha"]])
        self.assertEqual([item["sandbox"] for item in self.jobs], ["workspace-write", "read-only"])
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 2)

    def test_pending_ci_never_merges_or_spends_another_model_attempt(self):
        self.to_ci()
        self.broker.pr["statusCheckRollup"] = []
        self.step()
        self.step()
        self.assertEqual(self.cycle["phase"], "ci")
        self.assertEqual(self.broker.merges, [])
        self.assertEqual(len(self.jobs), 2)

    def test_ci_network_outage_waits_without_revision_and_recovers_same_head(self):
        self.to_ci()
        original_get = self.broker.get_pr
        calls = {"n": 0}

        def unavailable_once(number):
            calls["n"] += 1
            if calls["n"] == 1:
                raise NetworkUnavailable("offline")
            return original_get(number)

        self.broker.get_pr = unavailable_once
        self.step()
        self.assertEqual(self.cycle["phase"], "waiting_network")
        self.assertEqual(self.cycle["resume_phase"], "ci")
        self.assertEqual(self.cycle["revision"], 0)
        self.assertEqual(len(self.jobs), 2)
        self.cycle = self.auto.update_cycle(self.cycle["id"], phase="ci", resume_phase=None)
        self.step()
        self.assertEqual(self.cycle["phase"], "done")
        self.assertEqual(self.broker.merges, [self.cycle["reviewed_sha"]])

    def test_remote_merge_then_local_timeout_is_reconciled_without_second_merge(self):
        self.to_ci()
        original_merge = self.broker.merge

        def merged_then_timeout(number, sha):
            original_merge(number, sha)
            raise NetworkUnavailable("response lost after remote success")

        self.broker.merge = merged_then_timeout
        self.step()
        self.assertEqual(self.cycle["phase"], "waiting_network")
        self.assertEqual(self.cycle["resume_phase"], "merging")
        self.cycle = self.auto.update_cycle(self.cycle["id"], phase="merging", resume_phase=None)
        self.step()
        self.assertEqual(self.cycle["phase"], "done")
        self.assertEqual(len(self.broker.merges), 1)

    def test_author_provider_outage_keeps_revision_and_charges_failed_attempt(self):
        self.step()
        original = self.pipeline.executor
        calls = {"count": 0}

        def flaky(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return {"status": "failed", "summary": "Could not resolve model provider", "elapsed_seconds": 2}
            return original(*args, **kwargs)

        self.pipeline.executor = flaky
        self.step()
        self.assertEqual(self.cycle["phase"], "waiting_network")
        self.assertEqual(self.cycle["resume_phase"], "authoring")
        self.assertEqual(self.cycle["revision"], 0)
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 1)
        self.cycle = self.auto.update_cycle(self.cycle["id"], phase="authoring", resume_phase=None, provider_next_retry_at=0)
        self.step()
        self.assertEqual(self.cycle["phase"], "publishing")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 2)

    def test_review_provider_outage_does_not_escalate_reviewer_tier(self):
        for _ in range(3):
            self.step()
        self.assertEqual(self.cycle["phase"], "reviewing")
        original = self.pipeline.executor
        calls = {"count": 0}

        def flaky(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return {"status": "failed", "summary": "Failed to connect to provider", "elapsed_seconds": 3}
            return original(*args, **kwargs)

        self.pipeline.executor = flaky
        self.step()
        self.assertEqual(self.cycle["phase"], "waiting_network")
        self.assertEqual(self.cycle.get("review_attempt", 0), 0)
        self.assertEqual(self.cycle["revision"], 0)
        self.cycle = self.auto.update_cycle(self.cycle["id"], phase="reviewing", resume_phase=None, provider_next_retry_at=0)
        self.step()
        self.assertEqual(self.cycle["phase"], "ci")
        self.assertEqual(self.jobs[-1]["policy"]["model"], "gpt-6-sol")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 3)

    def test_uncertain_author_process_requires_attention_without_relaunch(self):
        self.step()
        self.pipeline.executor = lambda *args, **kwargs: {
            "status": "uncertain", "summary": "Worker process status is unknown", "elapsed_seconds": 4}
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 1)

    def test_planner_outage_persists_and_resumes_same_cycle(self):
        original = self.pipeline.executor
        calls = {"count": 0}

        def flaky(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return {"status": "failed", "summary": "Connection reset by peer", "elapsed_seconds": 1}
            return {"status": "completed", "summary": json.dumps({"tasks": [{
                "title": "A bounded follow-up", "role": "researcher",
                "description": "Investigate one bounded research question with evidence.",
                "acceptance": ["Report includes a falsifiable observation"]}]}), "elapsed_seconds": 1}

        self.pipeline.executor = flaky
        result = self.pipeline.plan()
        self.assertEqual(result["status"], "waiting_network")
        cycle, = [item for item in self.auto.list_cycles() if item["role"] == "planner"]
        self.assertEqual(cycle["phase"], "waiting_network")
        self.assertEqual(cycle["resume_phase"], "planning")
        cycle = self.auto.update_cycle(cycle["id"], phase="planning", resume_phase=None, provider_next_retry_at=0)
        self.pipeline.plan()
        resumed = self.auto.get_cycle(cycle["id"])
        self.assertEqual(resumed["phase"], "done")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 2)

    def test_planner_worktree_outage_resumes_queued_planner_after_restart(self):
        original = self.broker.prepare_worktree
        self.broker.prepare_worktree = Mock(side_effect=NetworkUnavailable("fetch offline"))
        self.assertEqual(self.pipeline.plan()["status"], "waiting_network")
        planner, = [c for c in self.auto.list_cycles() if c["role"] == "planner"]
        self.assertEqual(planner["resume_phase"], "queued")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 0)
        self.broker.prepare_worktree = original
        self.pipeline.executor = lambda *a, **k: {"status": "completed", "elapsed_seconds": 1,
            "summary": json.dumps({"tasks": [{"title": "New bounded research",
            "role": "researcher", "description": "Investigate one falsifiable small research question.",
            "acceptance": ["Evidence supports the result"]}]})}
        resumed = self.auto.update_cycle(planner["id"], phase="queued", resume_phase=None)
        restarted = Pipeline(self.root, self.store, self.auto, self.policy,
                             broker=self.broker, executor=self.pipeline.executor)
        self.assertEqual(restarted.advance(resumed)["status"], "planned")
        self.assertEqual(self.auto.get_cycle(planner["id"])["phase"], "done")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 1)

    def test_planner_worktree_auth_failure_requires_attention(self):
        from colony.network import AuthenticationFailure
        self.broker.prepare_worktree = Mock(side_effect=AuthenticationFailure("credentials invalid"))
        self.assertEqual(self.pipeline.plan()["status"], "needs_review")
        planner, = [c for c in self.auto.list_cycles() if c["role"] == "planner"]
        self.assertEqual(planner["phase"], "needs_review")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 0)

    def test_uncertain_process_network_summary_retains_full_charge_and_never_retries(self):
        for index, status in enumerate(["uncertain", "interrupted", "running"]):
            task = "UNCERTAIN-%s" % index
            self.store.seed([{"id": task, "title": "Scoped uncertain task", "role": "engineer",
                             "description": "Implement one scoped change", "acceptance": ["Verified result"]}])
            cycle = self.auto.create_cycle(task, "engineer")
            cycle = self.pipeline.advance(cycle)
            self.pipeline.executor = lambda *a, **k: {"status": status,
                "summary": "Connection reset while process remains unknown", "elapsed_seconds": 1}
            result = self.pipeline.advance(cycle)
            self.assertEqual(result["phase"], "needs_review")
            self.assertFalse(result.get("provider_network_offline", False))
            attempt, = self.auto.list_attempts(cycle["id"])
            self.assertEqual(attempt["status"], "interrupted")
            self.assertEqual(attempt["charged_seconds"], 10)
            self.assertEqual(result["revision"], 0)

    def test_uncertain_reviewer_network_summary_does_not_retry_or_escalate(self):
        for _ in range(3):
            self.step()
        self.pipeline.executor = lambda *a, **k: {"status": "uncertain",
            "summary": "Connection reset while reviewer process remains unknown", "elapsed_seconds": 1}
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertEqual(self.cycle.get("review_attempt", 0), 0)
        self.assertEqual(self.auto.list_attempts(self.cycle["id"])[-1]["charged_seconds"], 10)

    def test_worker_cleanup_uncertainty_retains_attempt_reservation(self):
        from colony.worker import WorkerProcessUncertain
        self.step()
        self.pipeline.executor = Mock(side_effect=WorkerProcessUncertain("termination unknown after connection reset"))
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        attempt, = self.auto.list_attempts(self.cycle["id"])
        self.assertEqual(attempt["status"], "interrupted")
        self.assertEqual(attempt["charged_seconds"], 10)
        self.assertFalse(self.cycle.get("provider_network_offline", False))

    def test_fair_dispatch_cannot_bypass_known_provider_outage(self):
        from colony.supervisor import Supervisor
        self.step()
        self.auto.update_cycle(self.cycle["id"], phase="waiting_network", resume_phase="authoring",
                               next_retry_at=9999999999, provider_network_offline=True,
                               provider_next_retry_at=9999999999, last_scheduled_order=0)
        self.store.seed([{"id": "T2", "title": "Another scoped task", "role": "engineer",
                         "description": "Implement another scoped case", "acceptance": ["Verified result"]}])
        second = self.pipeline.advance(self.auto.create_cycle("T2", "engineer"))
        self.auto.update_cycle(second["id"], last_scheduled_order=1)
        policy = dict(self.pipeline.policy, enabled=True)
        supervisor = Supervisor(self.root, self.store.path, policy,
                                pipeline=self.pipeline, task_store=self.store)
        self.addCleanup(supervisor.release_lock)
        self.assertEqual(supervisor.tick()["status"], "waiting_network")
        self.assertEqual(self.auto.get_cycle(second["id"])["phase"], "waiting_network")
        self.assertEqual(self.auto.get_budget(policy)["attempts"], 0)
        self.assertEqual(self.jobs, [])
        self.provider_probe.assert_not_called()

    def test_actual_triage_outage_reconnects_after_restart_and_replays_completed_handoff(self):
        import sys
        from colony.recovery import scan_recoveries
        from colony.supervisor import Supervisor
        from colony.worker import execute_job
        self.store.transition("T1", "blocked", "controller", summary="Original case needs repair")
        self.broker.pr = good_pr("a" * 40)
        self.store.set_task_artifacts("T1", branch="codex/original", pr_url=self.broker.pr["url"])
        self.auto.update_cycle(self.cycle["id"], phase="needs_review", pr_number=7,
                               pr_url=self.broker.pr["url"], head_sha="a" * 40,
                               base_sha="b" * 40, last_error="Original case needs repair")
        self.pipeline.policy.update(enabled=True, max_daily_attempts=2)
        scan_recoveries(self.store, self.auto, self.pipeline.policy)
        root = self.auto.get_cycle(self.cycle["id"])
        triage_id = root["recovery_triage_cycle_id"]
        binary = self.root / "fake-triage-provider"
        binary.write_text("#!" + sys.executable + "\nimport json,sys\nsys.stdin.read()\n"
                          "print(json.dumps({'type':'turn.failed','error':{'message':'Connection reset by provider'}}))\n")
        binary.chmod(0o755)
        self.pipeline.executor = execute_job
        supervisor = Supervisor(self.root, self.store.path, self.pipeline.policy,
                                pipeline=self.pipeline, task_store=self.store)
        self.addCleanup(supervisor.release_lock)
        with patch("colony.worker.shutil.which", return_value=str(binary)):
            self.assertEqual(supervisor.tick()["status"], "waiting_network")
        triage = self.auto.get_cycle(triage_id)
        self.assertEqual(triage["triage_network_retry_count"], 1)
        self.assertEqual(triage["resume_phase"], "triaging")
        self.assertEqual(self.auto.get_budget(self.pipeline.policy)["attempts"], 1)
        supervisor.release_lock()
        restarted_pipeline = Pipeline(self.root, self.store, self.auto, self.pipeline.policy,
                                      broker=self.broker, executor=execute_job)
        restarted = Supervisor(self.root, self.store.path, self.pipeline.policy,
                               pipeline=restarted_pipeline, task_store=self.store)
        self.addCleanup(restarted.release_lock)
        self.assertEqual(restarted.tick()["status"], "waiting_network")
        self.provider_probe.assert_not_called()
        self.auto.update_cycle(triage_id, next_retry_at=0, provider_next_retry_at=0)
        diagnosis = {"action": "repair", "diagnosis": "Repair the original missing case.",
                     "repair_title": "Repair the original required case",
                     "repair_description": "Implement the full original required acceptance without weakening it.",
                     "role": "engineer"}
        binary.write_text("#!" + sys.executable + "\nimport json,pathlib,sys\nsys.stdin.read()\n"
                          "pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(%r)\n"
                          "print(json.dumps({'type':'turn.completed','usage':{}}))\n" % json.dumps(diagnosis))
        with patch("colony.worker.shutil.which", return_value=str(binary)), \
                patch("colony.pipeline.apply_triage_result", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                restarted.tick()
        cached = self.auto.get_cycle(triage_id)
        self.assertEqual(cached["phase"], "triage_handoff")
        self.assertEqual(cached["triage_result"], diagnosis)
        attempts = self.auto.list_attempts(triage_id)
        self.assertEqual([a["stage"] for a in attempts], ["triage:0:net0", "triage:0:net1"])
        self.assertEqual([a["status"] for a in attempts], ["failed", "completed"])
        self.assertTrue(all(a["charged_seconds"] > 0 for a in attempts))
        self.assertEqual(self.auto.get_budget(self.pipeline.policy)["remaining_attempts"], 0)
        restarted.release_lock()
        final_pipeline = Pipeline(self.root, self.store, self.auto, self.pipeline.policy,
                                  broker=self.broker, executor=Mock(side_effect=AssertionError("No model may rerun")))
        final = Supervisor(self.root, self.store.path, self.pipeline.policy,
                           pipeline=final_pipeline, task_store=self.store)
        self.addCleanup(final.release_lock)
        final.tick()
        self.assertEqual(self.auto.get_cycle(triage_id)["phase"], "done")
        self.assertEqual(len(self.auto.list_attempts(triage_id)), 2)
        final_pipeline.executor.assert_not_called()
        repaired = self.auto.get_cycle(self.cycle["id"])
        self.assertIsNotNone(repaired["recovery_repair_cycle_id"])

    def test_actual_cli_provider_failure_waits_without_spending_revision(self):
        import sys
        from colony.worker import execute_job
        binary = self.root / "fake-provider-cli"
        binary.write_text("#!" + sys.executable + "\nimport json,sys\nsys.stdin.read()\n"
                          "print(json.dumps({'type':'turn.failed','error':{'message':'Connection reset by provider'}}))\n")
        binary.chmod(0o755)
        self.pipeline.policy["allow_implementation"] = True
        self.pipeline.executor = execute_job
        self.step()
        with patch("colony.worker.shutil.which", return_value=str(binary)):
            self.step()
        self.assertEqual(self.cycle["phase"], "waiting_network")
        self.assertEqual(self.cycle["revision"], 0)
        self.assertTrue(self.cycle["provider_network_offline"])
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 1)

    def test_uncertain_planner_network_summary_requires_attention(self):
        self.pipeline.executor = lambda *a, **k: {"status": "uncertain",
            "summary": "Connection reset; process unknown", "elapsed_seconds": 1}
        self.assertEqual(self.pipeline.plan()["status"], "needs_review")
        planner, = [c for c in self.auto.list_cycles() if c["role"] == "planner"]
        self.assertEqual(self.auto.list_attempts(planner["id"])[0]["charged_seconds"], 10)

    def test_provider_outage_blocks_other_cycles_and_survives_restart_until_probe(self):
        self.step()
        self.pipeline.executor = Mock(return_value={"status": "failed",
            "summary": "Failed to connect to model provider", "elapsed_seconds": 1})
        self.step()
        self.assertTrue(self.cycle["provider_network_offline"])
        self.store.seed([{"id": "T2", "title": "Second scoped task", "role": "engineer",
                         "description": "Implement another scoped procedure", "acceptance": ["Verified result"]}])
        second = self.pipeline.advance(self.auto.create_cycle("T2", "engineer"))
        restarted = Pipeline(self.root, self.store, self.auto, self.policy,
                             broker=self.broker, executor=self.executor)
        waiting = restarted.advance(second)
        self.assertEqual(waiting["phase"], "waiting_network")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 1)
        self.provider_probe.assert_not_called()
        self.auto.update_cycle(self.cycle["id"], provider_next_retry_at=0)
        self.provider_probe.side_effect = NetworkUnavailable("still offline")
        resumed = self.auto.update_cycle(second["id"], phase="authoring", resume_phase=None)
        self.assertEqual(restarted.advance(resumed)["phase"], "waiting_network")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 1)
        self.auto.update_cycle(self.cycle["id"], provider_next_retry_at=0)
        self.provider_probe.side_effect = None
        resumed = self.auto.update_cycle(second["id"], phase="authoring", resume_phase=None)
        self.assertEqual(restarted.advance(resumed)["phase"], "publishing")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 2)
        self.assertFalse(self.auto.get_cycle(self.cycle["id"])["provider_network_offline"])
        self.assertEqual(self.jobs[-1]["policy"]["model"], "gpt-6-luna")

    def test_revision_publication_persists_prior_head_across_lost_response(self):
        for _ in range(3):
            self.step()
        old = self.cycle["head_sha"]
        self.cycle = self.auto.update_cycle(self.cycle["id"], phase="publishing")
        self.broker.commit = Mock(return_value="c" * 40)
        self.broker.publish = Mock(side_effect=NetworkUnavailable("push response lost"))
        self.step()
        self.assertEqual(self.cycle["publish_previous_head_sha"], old)
        self.assertEqual(self.cycle["publish_candidate_sha"], "c" * 40)
        self.broker.publish = Mock(return_value=good_pr("c" * 40))
        resumed = self.auto.update_cycle(self.cycle["id"], phase="publishing", resume_phase=None)
        restarted = Pipeline(self.root, self.store, self.auto, self.policy,
                             broker=self.broker, executor=self.executor)
        self.cycle = restarted.advance(resumed)
        published = self.broker.publish.call_args[0][0]
        self.assertEqual(published["publish_previous_head_sha"], old)
        self.assertEqual(self.cycle["published_head_sha"], "c" * 40)
        self.assertEqual(self.cycle["phase"], "reviewing")

    def test_local_timeout_and_authentication_do_not_enter_network_wait(self):
        self.step()
        original = self.pipeline.executor
        self.pipeline.executor = lambda *args, **kwargs: {
            "status": "failed", "summary": "Local worker timed out", "elapsed_seconds": 10}
        self.step()
        self.assertEqual(self.cycle["phase"], "authoring")
        self.assertEqual(self.cycle["revision"], 1)
        self.cycle = self.auto.update_cycle(self.cycle["id"], phase="authoring", revision=0,
                                            feedback=None, reviewed_sha=None, review=None,
                                            author_completed=False, author_network_retry_count=1)
        self.pipeline.executor = lambda *args, **kwargs: {
            "status": "failed", "summary": "HTTP 401: Bad credentials", "elapsed_seconds": 1}
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertEqual(self.auto.get_budget(self.policy)["attempts"], 2)

    def test_external_head_change_and_merge_never_claims_checked_success(self):
        self.to_ci()
        self.broker.pr.update(state="MERGED", mergedAt="now", headRefOid="e" * 40)
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertNotEqual(self.store.get_task("T1")["status"], "done")

    def test_external_merge_without_ci_evidence_needs_review(self):
        self.to_ci()
        self.broker.pr.update(state="MERGED", mergedAt="now", statusCheckRollup=[])
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")

    def test_review_changes_request_bounded_stronger_revision(self):
        self.review = {"verdict": "changes_requested", "summary": "Missing recursive case", "findings": ["Prove the successor case"]}
        self.to_ci = None
        for _ in range(4):
            self.step()
        self.assertEqual(self.cycle["phase"], "authoring")
        self.assertEqual(self.cycle["revision"], 1)
        self.step()
        self.assertEqual(self.jobs[-1]["policy"]["model"], "gpt-6-sol")
        self.assertIn("Missing recursive case", self.jobs[-1]["prompt"])

    def test_review_publication_resumes_without_repeating_model_review(self):
        self.to_ci()
        cycle = self.auto.update_cycle(self.cycle["id"], phase="review_publication")
        self.cycle = self.pipeline.advance(cycle)
        self.assertEqual(self.cycle["phase"], "ci")
        self.assertEqual(len(self.jobs), 2)

    def test_failure_ci_feedback_includes_actual_bounded_log(self):
        self.to_ci()
        self.broker.pr["statusCheckRollup"][1]["conclusion"] = "FAILURE"
        self.step()
        self.assertEqual(self.cycle["phase"], "authoring")
        self.assertIn("unknown identifier example", self.cycle["feedback"])

    def test_budget_refusal_leaves_task_ready(self):
        self.step()
        self.pipeline.policy["max_daily_seconds"] = 1
        with self.assertRaises(BudgetExceeded):
            self.step()
        self.assertEqual(self.store.get_task("T1")["status"], "ready")
        self.assertEqual(self.jobs, [])

    def test_duplicate_author_attempt_is_not_reexecuted(self):
        self.step()
        self.step()
        self.auto.update_cycle(self.cycle["id"], phase="authoring")
        self.step()
        self.assertEqual(len(self.jobs), 1)
        self.assertEqual(self.cycle["phase"], "needs_review")

    def test_review_failure_escalates_without_approving(self):
        for _ in range(3):
            self.step()
        original = self.pipeline.executor
        self.pipeline.executor = lambda *args, **kwargs: {"status": "failed", "summary": "Model unavailable", "elapsed_seconds": 1}
        self.step()
        self.assertEqual(self.cycle["phase"], "reviewing")
        self.assertEqual(self.cycle["review_attempt"], 1)
        self.pipeline.executor = original
        self.step()
        self.assertEqual(self.jobs[-1]["policy"]["model"], "gpt-6.1-sol")
        self.assertEqual(self.cycle["phase"], "ci")

    def test_known_machine_paths_are_redacted_before_publication(self):
        self.assertEqual(self.pipeline._output({"summary": "File " + str(self.root / "x")}, {}), "File <repository>/x")

    def use_sre_task(self):
        self.store.seed([{"id": "S1", "title": "Recover transient network failures", "role": "sre",
                          "description": "Implement a bounded retry for transient network failures.",
                          "acceptance": ["A bounded failure produces an actionable status"]}])
        self.cycle = self.auto.create_cycle("S1", "sre")

    def test_sre_gets_write_scope_and_stronger_independent_review(self):
        self.use_sre_task()
        self.to_ci()
        self.assertEqual(self.jobs[0]["sandbox"], "workspace-write")
        self.assertEqual(self.jobs[0]["policy"]["role"], "sre")
        self.assertIn("colony/network_recovery.py", self.jobs[0]["prompt"])
        self.assertIn("separate governance PR", self.jobs[0]["prompt"])
        self.assertEqual(self.jobs[1]["sandbox"], "read-only")
        self.assertEqual(self.jobs[1]["policy"]["role"], "reviewer")
        self.assertEqual(self.jobs[1]["policy"]["model"], "gpt-6-sol")
        self.assertFalse((self.root / "checkout/research/colony/s1.md").exists())

    def test_approved_green_sre_hands_off_without_merging_even_after_restart(self):
        self.use_sre_task()
        self.to_ci()
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertTrue(self.cycle["governance_required"])
        self.assertEqual(self.cycle["governance_status"], "awaiting_controller_integration")
        self.assertEqual(self.cycle["ci_status"], "passed")
        self.assertIsNone(self.cycle["last_error"])
        self.assertEqual(self.store.get_task("S1")["status"], "review")
        self.assertEqual(self.broker.merges, [])
        events = self.store.snapshot()["events"]
        self.assertEqual(sum(item["kind"] == "governance.ready" for item in events), 1)
        self.assertFalse(any(item["kind"] in {"cycle.failed", "cycle.needs_review"} for item in events))
        restarted = Pipeline(self.root, self.store, self.auto, self.policy,
                             broker=self.broker, executor=self.executor)
        resumed = restarted.advance(self.auto.get_cycle(self.cycle["id"]))
        self.assertEqual(resumed["governance_status"], "awaiting_controller_integration")
        self.assertEqual(self.broker.merges, [])
        self.assertEqual(len(self.jobs), 2)

    def test_sre_handoff_waits_for_required_ci_and_does_not_require_automatic_merge(self):
        self.use_sre_task()
        self.to_ci()
        self.broker.pr["statusCheckRollup"] = []
        self.step()
        self.assertEqual(self.cycle["phase"], "ci")
        self.assertNotEqual(self.cycle.get("governance_status"), "awaiting_controller_integration")
        self.broker.pr = good_pr(self.cycle["reviewed_sha"])
        self.pipeline.policy["automatic_merge"] = False
        self.step()
        self.assertEqual(self.cycle["governance_status"], "awaiting_controller_integration")
        self.assertEqual(self.broker.merges, [])

    def test_external_sre_merge_still_requires_exact_head_review_and_ci(self):
        self.use_sre_task()
        self.to_ci()
        self.broker.pr.update(state="MERGED", mergedAt="now", headRefOid="e" * 40)
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertNotEqual(self.store.get_task("S1")["status"], "done")
        self.assertEqual(self.broker.merges, [])

    def test_planner_schema_runtime_validation_and_prompt_accept_sre_governance(self):
        roles = PLAN_SCHEMA["properties"]["tasks"]["items"]["properties"]["role"]["enum"]
        self.assertIn("sre", roles)
        proposed = {"title": "Recover transient network errors", "role": "sre",
                    "description": "Implement bounded retries for transient GitHub network errors.",
                    "acceptance": ["Retries stop at the configured bound"]}

        def plan_executor(*args, **kwargs):
            self.assertIn("role sre", args[2])
            self.assertIn("controller-integration handoff", args[2])
            self.assertIn("colony/network_recovery.py", args[2])
            return {"status": "completed", "summary": json.dumps({"tasks": [proposed]}), "elapsed_seconds": 1}

        self.pipeline.executor = plan_executor
        result = self.pipeline.plan()
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["tasks"][0]["role"], "sre")
        self.assertEqual(self.store.get_task(result["tasks"][0]["id"])["status"], "ready")

    def use_operations_task(self):
        self.store.seed([{"id": "O1", "title": "Audit swarm work and missing roles", "role": "operations",
                          "description": "Audit concrete recurring failures, queued work, and missing role charters.",
                          "acceptance": ["Identify an evidence-backed bottleneck and bounded follow-up work"]}])
        self.cycle = self.auto.create_cycle("O1", "operations")
        self.operations_report = {
            "report": "Repeated bounded author failures delay proof experiments; measure the next scoped retry.",
            "role_proposals": ["A profiling specialist could measure tactic time after a separate role review."],
            "follow_up_tasks": [{"title": "Measure one bounded tactic experiment", "role": "researcher",
                                 "description": "Record the actual result of one bounded proof experiment and its stop condition.",
                                 "acceptance": ["State actual evidence and a falsifiable next experiment"]}],
        }
        base_executor = self.executor

        def operations_executor(*args, **kwargs):
            result = base_executor(*args, **kwargs)
            if kwargs.get("output_schema") == OPS_SCHEMA:
                result["summary"] = json.dumps(self.operations_report)
            return result

        self.pipeline.executor = operations_executor

    def follow_up_tasks(self):
        return [task for task in self.store.snapshot()["tasks"] if task["id"].startswith("OPSFOLLOW-")]

    def test_operations_author_is_readonly_and_publishes_validated_structured_report(self):
        self.use_operations_task()
        self.step()
        self.step()
        self.assertEqual(self.jobs[0]["sandbox"], "read-only")
        self.assertEqual(self.jobs[0]["output_schema"], OPS_SCHEMA)
        self.assertIn("READ ONLY operations steward", self.jobs[0]["prompt"])
        self.assertIn("task_status_counts", self.jobs[0]["prompt"])
        self.assertIn("role_charters", self.jobs[0]["prompt"])
        self.assertIn("grant no authority", self.jobs[0]["prompt"])
        self.assertEqual(self.cycle["operations_report"], self.operations_report)
        report = (self.root / "checkout/research/colony/o1.md").read_text()
        self.assertIn(self.operations_report["report"], report)
        self.assertIn(self.operations_report["role_proposals"][0], report)
        self.assertFalse(self.cycle["summary"].startswith("{"))
        self.assertEqual(self.follow_up_tasks(), [])

    def test_operations_followups_wait_for_review_ci_and_exact_head_merge(self):
        self.use_operations_task()
        for _ in range(4):
            self.step()
            self.assertEqual(self.follow_up_tasks(), [])
        self.assertEqual(self.cycle["phase"], "ci")
        self.broker.pr["statusCheckRollup"] = []
        self.step()
        self.assertEqual(self.follow_up_tasks(), [])
        self.broker.pr = good_pr(self.cycle["reviewed_sha"])
        self.step()
        self.assertEqual(self.cycle["phase"], "done")
        followups = self.follow_up_tasks()
        self.assertEqual(len(followups), 1)
        self.assertEqual(followups[0]["role"], "researcher")
        self.assertEqual(self.cycle["follow_up_task_ids"], [followups[0]["id"]])
        self.assertEqual(self.broker.merges, [self.cycle["reviewed_sha"]])
        # Reconciliation after a crash around follow-up recording seeds the same
        # deterministic IDs rather than producing another batch.
        self.cycle = self.auto.update_cycle(self.cycle["id"], phase="ci")
        self.step()
        self.assertEqual(len(self.follow_up_tasks()), 1)
        self.assertEqual(self.cycle["follow_up_task_ids"], [followups[0]["id"]])

    def test_operations_external_wrong_head_merge_never_enqueues_followups(self):
        self.use_operations_task()
        self.to_ci()
        self.broker.pr.update(state="MERGED", mergedAt="now", headRefOid="e" * 40)
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertEqual(self.follow_up_tasks(), [])

    def test_operations_cannot_grant_a_new_followup_role(self):
        self.use_operations_task()
        self.operations_report["follow_up_tasks"][0]["role"] = "administrator"
        self.step()
        self.step()
        self.assertEqual(self.cycle["phase"], "needs_review")
        self.assertEqual(self.follow_up_tasks(), [])
        self.assertEqual(self.broker.publications, [])

    def test_planner_cannot_bypass_single_pending_operations_scheduler(self):
        self.assertNotIn("operations", PLAN_SCHEMA["properties"]["tasks"]["items"]["properties"]["role"]["enum"])
        proposal = {"title": "Audit recurring swarm bottlenecks", "role": "operations",
                    "description": "Read completed task evidence and propose bounded work for existing roles.",
                    "acceptance": ["Report bottlenecks with actual task evidence"]}

        def planner(*args, **kwargs):
            self.assertIn("Do not create\noperations tasks", args[2])
            return {"status": "completed", "summary": json.dumps({"tasks": [proposal]}), "elapsed_seconds": 1}

        self.pipeline.executor = planner
        with self.assertRaises(PublicationRejected):
            self.pipeline.plan()
        self.assertFalse(any(task["role"] == "operations" for task in self.store.snapshot()["tasks"]))


if __name__ == "__main__":
    unittest.main()
