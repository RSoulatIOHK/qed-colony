from pathlib import Path
import tempfile
import threading
import unittest

from colony.autonomy_store import AutonomyStore, BudgetExceeded
from colony.store import Store
from colony.supervisor import Supervisor, SupervisorAlreadyRunning


class FakePipeline:
    def __init__(self, autonomy):
        self.autonomy = autonomy
        self.advanced = []
        self.plans = 0
        self.error = None

    def advance(self, cycle):
        self.advanced.append(cycle["id"])
        if self.error:
            raise self.error
        phase = "ci" if cycle["phase"] == "queued" else "done"
        self.autonomy.update_cycle(cycle["id"], phase=phase)
        return {"message": "Advanced " + phase}

    def plan(self):
        self.plans += 1
        return {"status": "idle"}


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "state.db"
        self.tasks = Store(self.path).initialize()
        self.autonomy = AutonomyStore(self.path).initialize()
        self.pipeline = FakePipeline(self.autonomy)
        self.policy = {"enabled": True, "max_daily_seconds": 600, "max_daily_attempts": 3}
        self.supervisor = self.make_supervisor()

    def make_supervisor(self):
        supervisor = Supervisor(self.root, self.path, self.policy, self.pipeline, self.tasks)
        self.addCleanup(supervisor.release_lock)
        return supervisor

    def seed(self):
        self.tasks.seed([{"id": "low", "title": "Low", "role": "researcher", "priority": 1},
                         {"id": "high", "title": "High", "role": "engineer", "priority": 10}])

    def test_ticks_finish_existing_ci_before_admitting_next_ready_task(self):
        self.seed()
        self.supervisor.tick()
        first = self.autonomy.list_cycles()[0]
        self.assertEqual(first["task_id"], "high")
        self.supervisor.tick()
        cycles = self.autonomy.list_cycles()
        self.assertEqual([cycle["task_id"] for cycle in cycles], ["high", "low"])
        self.assertEqual(self.pipeline.advanced, [first["id"], first["id"], cycles[1]["id"]])
        self.assertEqual(cycles[0]["phase"], "done")

    def test_controller_lock_prevents_two_dispatchers(self):
        self.supervisor.startup()
        second = self.make_supervisor()
        with self.assertRaises(SupervisorAlreadyRunning):
            second.tick()
        self.supervisor.release_lock()
        second.startup()

    def test_restart_keeps_cycle_and_does_not_duplicate_dispatch(self):
        self.seed()
        self.supervisor.tick()
        original = self.autonomy.next_cycle()["id"]
        self.supervisor.release_lock()
        self.make_supervisor().tick()
        cycles = self.autonomy.list_cycles()
        self.assertEqual([cycle["task_id"] for cycle in cycles], ["high", "low"])
        self.assertEqual(self.pipeline.advanced, [original, original, cycles[1]["id"]])
        self.assertEqual(sum(cycle["id"] == original for cycle in cycles), 1)

    def test_interrupted_model_is_not_blindly_repeated(self):
        self.tasks.seed([{"id": "T1", "title": "Task", "role": "engineer"}])
        cycle = self.autonomy.create_cycle("T1", "engineer")
        self.autonomy.reserve_attempt(cycle["id"], "author", 300, self.policy)
        self.supervisor.tick()
        self.assertEqual(self.autonomy.get_cycle(cycle["id"])["phase"], "needs_review")
        self.assertEqual(self.pipeline.advanced, [])
        self.assertEqual(len(self.autonomy.list_cycles()), 1)

    def test_budget_exhaustion_blocks_new_planning_and_dispatch(self):
        cycle = self.autonomy.create_cycle("old", "engineer")
        self.autonomy.reserve_attempt(cycle["id"], "author", 600, self.policy)
        self.autonomy.finish_attempt(1, 600)
        self.autonomy.update_cycle(cycle["id"], phase="done")
        self.seed()
        result = self.supervisor.tick()
        self.assertEqual(result["status"], "budget_limited")
        self.assertEqual(self.pipeline.advanced, [])
        self.assertEqual(self.pipeline.plans, 0)

    def test_ci_can_still_advance_with_no_model_budget(self):
        cycle = self.autonomy.create_cycle("old", "engineer")
        attempt = self.autonomy.reserve_attempt(cycle["id"], "author", 600, self.policy)
        self.autonomy.finish_attempt(attempt, 600)
        self.autonomy.update_cycle(cycle["id"], phase="ci")
        self.supervisor.tick()
        self.assertEqual(self.autonomy.get_cycle(cycle["id"])["phase"], "done")

    def test_empty_queue_is_healthy_waiting_and_rechecks_planner(self):
        self.assertEqual(self.supervisor.tick()["status"], "waiting")
        self.assertEqual(self.supervisor.tick()["status"], "waiting")
        self.assertEqual(self.pipeline.plans, 2)
        self.assertEqual(self.autonomy.service_snapshot()["status"], "waiting")

    def test_disabled_policy_never_launches(self):
        self.supervisor.policy["enabled"] = False
        self.seed()
        self.assertEqual(self.supervisor.tick()["status"], "disabled")
        self.assertEqual(self.pipeline.advanced, [])

    def test_budget_denial_keeps_phase_for_next_day(self):
        self.seed()
        self.pipeline.error = BudgetExceeded("Cannot reserve")
        result = self.supervisor.tick()
        self.assertEqual(result["status"], "budget_limited")
        self.assertEqual(self.autonomy.next_cycle()["phase"], "queued")

    def test_forever_stops_early_and_releases_singleton(self):
        stop = threading.Event()
        stop.set()
        self.supervisor.run_forever(stop_event=stop, poll_seconds=0.01)
        self.assertEqual(self.autonomy.service_snapshot()["status"], "stopped")
        self.make_supervisor().acquire_lock()

    def test_periodic_operations_audit_dispatches_before_new_research(self):
        for number in range(3):
            cycle = self.autonomy.create_cycle("old-%s" % number, "engineer")
            self.autonomy.update_cycle(cycle["id"], phase="done")
        self.seed()
        self.supervisor.tick()
        cycle = self.autonomy.next_cycle()
        self.assertEqual(cycle["task_id"], "OPS001")
        self.assertEqual(cycle["role"], "operations")

    def test_pending_ci_advances_without_scheduling_audit(self):
        for number in range(3):
            old = self.autonomy.create_cycle("old-%s" % number, "engineer")
            self.autonomy.update_cycle(old["id"], phase="done")
        active = self.autonomy.create_cycle("active", "engineer")
        self.autonomy.update_cycle(active["id"], phase="ci")
        self.supervisor.tick()
        self.assertEqual(self.autonomy.get_cycle(active["id"])["phase"], "done")
        self.assertIsNone(self.tasks.get_task("OPS001"))


if __name__ == "__main__":
    unittest.main()
