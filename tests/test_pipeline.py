import json
from pathlib import Path
import tempfile
import unittest

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
