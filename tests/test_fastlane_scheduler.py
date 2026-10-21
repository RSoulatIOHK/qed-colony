"""Regression: a serial model call used to delay already completed PR stages.

Acceptance: publish every ready artifact before another author, review public
candidates first, finish approved candidates before authorship, poll each pending
CI cycle once per pass, and drain saved stages even when the model cap is zero.
The rejected alternative is unconditional CI priority, which starves model work
whenever a check remains pending. Model execution remains synchronous and single.
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from colony.autonomy_store import AutonomyStore, BudgetExceeded
from colony.store import Store
from colony.supervisor import Supervisor


class StagePipeline:
    def __init__(self, autonomy):
        self.autonomy = autonomy
        self.advanced = []
        self.model_calls = []
        self.merged = []
        self.deny_models = False

    def advance(self, cycle):
        self.advanced.append((cycle["task_id"], cycle["phase"]))
        phase = cycle["phase"]
        if phase in {"authoring", "reviewing", "triaging"}:
            self.model_calls.append(cycle["task_id"])
            if self.deny_models:
                raise BudgetExceeded("No reservation remains")
        if phase == "queued":
            self.autonomy.update_cycle(cycle["id"], phase="authoring")
        elif phase == "publishing":
            self.autonomy.update_cycle(cycle["id"], phase="reviewing")
        elif phase in {"review_publication", "reviewing"}:
            self.autonomy.update_cycle(cycle["id"], phase="ci")
        elif phase in {"ci", "merging"} and not cycle.get("pending"):
            self.merged.append(cycle["task_id"])
            self.autonomy.update_cycle(cycle["id"], phase="done")
        elif phase == "triage_handoff":
            self.autonomy.update_cycle(cycle["id"], phase="done")
        return {"message": "Recorded stage"}

    def plan(self):
        raise AssertionError("No speculative planning while existing cycles advance")


class FastLaneSchedulingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.db"
        self.tasks = Store(self.path).initialize()
        self.autonomy = AutonomyStore(self.path).initialize()
        self.pipeline = StagePipeline(self.autonomy)
        self.policy = {"enabled": True, "max_daily_seconds": 0, "max_daily_attempts": 0}
        self.supervisor = Supervisor(self.root, self.path, self.policy, self.pipeline, self.tasks)
        self.addCleanup(self.supervisor.release_lock)

    def cycle(self, task_id, phase, **data):
        self.tasks.seed([{"id": task_id, "title": "Scoped " + task_id, "role": "engineer"}])
        cycle = self.autonomy.create_cycle(task_id, "engineer")
        return self.autonomy.update_cycle(cycle["id"], phase=phase, **data)

    def test_two_completed_authors_publish_before_another_author_starts(self):
        self.cycle("AUTHOR", "authoring")
        self.cycle("FIRST", "publishing")
        self.cycle("SECOND", "publishing")
        self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced[:2], [("FIRST", "publishing"), ("SECOND", "publishing")])
        self.assertEqual(len(self.pipeline.model_calls), 1)
        self.assertIn(self.pipeline.model_calls[0], {"FIRST", "SECOND"})
        self.assertNotIn("AUTHOR", self.pipeline.model_calls)

    def test_saved_approval_publishes_and_merges_before_next_author(self):
        self.cycle("AUTHOR", "authoring")
        self.cycle("APPROVED", "review_publication")
        self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced, [("APPROVED", "review_publication"),
                                                   ("APPROVED", "ci"), ("AUTHOR", "authoring")])
        self.assertEqual(self.pipeline.merged, ["APPROVED"])
        self.assertEqual(self.pipeline.model_calls, ["AUTHOR"])

    def test_pending_ci_is_polled_once_and_cannot_monopolize_dispatch(self):
        self.cycle("PENDING", "ci", pending=True)
        self.cycle("AUTHOR", "authoring")
        self.supervisor.tick()
        self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced, [("PENDING", "ci"), ("AUTHOR", "authoring")] * 2)
        self.assertEqual(self.pipeline.model_calls, ["AUTHOR", "AUTHOR"])

    def test_pending_ci_admits_a_real_ready_task_without_a_cycle(self):
        self.supervisor.policy.update(max_daily_seconds=600, max_daily_attempts=3)
        self.cycle("PENDING", "ci", pending=True)
        self.tasks.seed([{"id": "READY", "title": "Already scoped work", "role": "engineer",
                          "status": "ready", "acceptance": ["Original specified acceptance"]}])
        with patch("colony.operations.maybe_enqueue_audit") as audit:
            self.supervisor.tick()
            self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced, [("PENDING", "ci"), ("READY", "queued"),
                                                   ("PENDING", "ci"), ("READY", "authoring")])
        self.assertEqual(self.pipeline.model_calls, ["READY"])
        ready_cycles = [cycle for cycle in self.autonomy.list_cycles() if cycle["task_id"] == "READY"]
        self.assertEqual(len(ready_cycles), 1)
        self.assertEqual(self.tasks.get_task("READY")["acceptance"], ["Original specified acceptance"])
        audit.assert_not_called()

    def test_pending_ci_does_not_admit_ready_task_when_daily_budget_is_zero(self):
        self.cycle("PENDING", "ci", pending=True)
        self.tasks.seed([{"id": "READY", "title": "Already scoped work", "role": "engineer", "status": "ready"}])
        result = self.supervisor.tick()
        self.assertEqual(result["status"], "budget_limited")
        self.assertEqual(self.pipeline.advanced, [("PENDING", "ci")])
        self.assertEqual(self.pipeline.model_calls, [])
        self.assertEqual([cycle["task_id"] for cycle in self.autonomy.list_cycles()], ["PENDING"])
        self.assertEqual(self.tasks.get_task("READY")["status"], "ready")

    def test_existing_public_review_precedes_older_author_and_then_drains(self):
        self.cycle("AUTHOR", "authoring", last_scheduled_order=0)
        self.cycle("REVIEW", "reviewing", last_scheduled_order=100)
        self.supervisor.tick()
        self.assertEqual(self.pipeline.model_calls, ["REVIEW"])
        self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced, [("REVIEW", "reviewing"), ("REVIEW", "ci"),
                                                   ("AUTHOR", "authoring")])
        self.assertEqual(self.pipeline.merged, ["REVIEW"])

    def test_no_model_budget_still_drains_all_saved_controller_stages(self):
        self.cycle("PENDING", "ci", pending=True)
        self.cycle("MERGED", "merging")
        self.cycle("APPROVED", "review_publication")
        self.cycle("HANDOFF", "triage_handoff", recovery_kind="triage")
        self.cycle("PUBLICATION", "publishing")
        self.pipeline.deny_models = True
        result = self.supervisor.tick()
        self.assertEqual(result["status"], "budget_limited")
        self.assertEqual(self.pipeline.advanced[:-1], [("PENDING", "ci"), ("MERGED", "merging"),
                                                      ("APPROVED", "review_publication"), ("APPROVED", "ci"),
                                                      ("HANDOFF", "triage_handoff"), ("PUBLICATION", "publishing")])
        self.assertEqual(self.pipeline.model_calls, ["PUBLICATION"])
        self.assertEqual(self.pipeline.merged, ["MERGED", "APPROVED"])
        self.assertEqual(self.autonomy.list_attempts(), [])

    def test_review_group_round_robin_survives_restart(self):
        self.cycle("AUTHOR", "authoring")
        first = self.cycle("FIRST", "reviewing")
        second = self.cycle("SECOND", "reviewing")
        self.supervisor.tick()
        self.supervisor.release_lock()
        restarted = Supervisor(self.root, self.path, self.policy, self.pipeline, self.tasks)
        self.addCleanup(restarted.release_lock)
        restarted.tick()
        restarted.tick()
        self.assertEqual(self.pipeline.model_calls, [first["task_id"], second["task_id"], "AUTHOR"])

    def test_triage_kind_with_unsaved_handoff_is_never_a_controller_stage(self):
        cycle = self.cycle("TRIAGE", "publishing", recovery_kind="triage")
        self.assertFalse(self.supervisor._controller_stage(cycle))


if __name__ == "__main__":
    unittest.main()
