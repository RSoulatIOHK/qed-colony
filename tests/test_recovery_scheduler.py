"""Recovery ownership and fairness must not depend on a model call succeeding."""

from pathlib import Path
import tempfile
import unittest

from colony.autonomy_store import AutonomyStore, BudgetExceeded
from colony.recovery import scan_recoveries
from colony.store import Store
from colony.supervisor import Supervisor


class RecordingPipeline:
    def __init__(self):
        self.advanced = []
        self.errors = {}

    def advance(self, cycle):
        self.advanced.append(cycle["id"])
        if cycle["id"] in self.errors:
            raise self.errors[cycle["id"]]
        return {"message": "Recorded nonblocking dispatch"}

    def plan(self):
        raise AssertionError("Existing runnable cycles must be dispatched before planning")


class RecoverySchedulingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.db"
        self.tasks = Store(self.path).initialize()
        self.autonomy = AutonomyStore(self.path).initialize()
        self.pipeline = RecordingPipeline()
        self.policy = {"enabled": True, "max_daily_seconds": 0, "max_daily_attempts": 0}
        self.supervisor = self.make_supervisor()

    def make_supervisor(self):
        supervisor = Supervisor(self.root, self.path, self.policy, self.pipeline, self.tasks)
        self.addCleanup(supervisor.release_lock)
        return supervisor

    def cycle(self, task_id, phase, **data):
        self.tasks.seed([{"id": task_id, "title": "Scoped " + task_id, "role": "engineer",
                          "description": "Implement the full original required case.",
                          "acceptance": ["Preserve original acceptance"],
                          "status": "blocked" if phase == "needs_review" else "ready"}])
        cycle = self.autonomy.create_cycle(task_id, "engineer")
        return self.autonomy.update_cycle(cycle["id"], phase=phase, **data)

    def parked(self):
        return self.cycle("PARKED", "needs_review", pr_url="https://github.com/example/repo/pull/5",
                          pr_number=5, head_sha="a" * 40, last_error="Original bounded review exhausted")

    def test_scan_assigns_owner_before_pending_ci_and_zero_budget_dispatch(self):
        ci = self.cycle("CI", "ci")
        root = self.parked()
        self.supervisor.tick()
        assigned = self.autonomy.get_cycle(root["id"])
        self.assertEqual(assigned["recovery_owner"], "blocker-triage")
        self.assertEqual(assigned["recovery_status"], "triage_queued")
        triage = assigned["recovery_triage_cycle_id"]
        self.assertEqual(self.pipeline.advanced, [ci["id"]])
        self.assertEqual(self.autonomy.list_attempts(), [])
        self.pipeline.errors[triage] = BudgetExceeded("No model reservation available")
        self.assertEqual(self.supervisor.tick()["status"], "budget_limited")
        self.assertEqual(self.autonomy.get_cycle(triage)["phase"], "triaging")
        self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced, [ci["id"], triage, ci["id"]])

    def test_round_robin_persists_across_restart_without_ci_starvation(self):
        ci = self.cycle("CI", "ci")
        root = self.parked()
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        triage = self.autonomy.get_cycle(root["id"])["recovery_triage_cycle_id"]
        ordinary = self.cycle("ORDINARY", "queued")
        for _ in range(3):
            self.supervisor.tick()
        expected = [ci["id"], triage, ordinary["id"]]
        self.assertEqual(self.pipeline.advanced, expected)
        self.supervisor.release_lock()
        restarted = self.make_supervisor()
        for _ in range(3):
            restarted.tick()
        self.assertEqual(self.pipeline.advanced, expected + expected)

    def test_dispatch_error_parks_selected_cycle_instead_of_oldest_cycle(self):
        oldest = self.cycle("OLDEST", "ci", last_scheduled_order=20)
        selected = self.cycle("SELECTED", "authoring", last_scheduled_order=0)
        self.pipeline.errors[selected["id"]] = RuntimeError("Dispatch failed")
        result = self.supervisor.tick()
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(self.pipeline.advanced, [selected["id"]])
        self.assertEqual(self.autonomy.get_cycle(selected["id"])["phase"], "needs_review")
        self.assertEqual(self.autonomy.get_cycle(oldest["id"])["phase"], "ci")
        errors = [event for event in self.tasks.snapshot()["events"] if event["kind"] == "autonomy.error"]
        self.assertEqual(errors[-1]["task_id"], "SELECTED")


if __name__ == "__main__":
    unittest.main()
