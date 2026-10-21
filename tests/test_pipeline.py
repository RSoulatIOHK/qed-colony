import json
from pathlib import Path
import tempfile
import unittest

from colony.autonomy_store import AutonomyStore, BudgetExceeded
from colony.pipeline import Pipeline
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


if __name__ == "__main__":
    unittest.main()
