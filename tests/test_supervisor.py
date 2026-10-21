from pathlib import Path
import tempfile
import threading
import unittest

from colony.autonomy_store import AutonomyStore, BudgetExceeded
from colony.network import NetworkUnavailable
from colony.store import Store
from colony.supervisor import Supervisor, SupervisorAlreadyRunning


class FakePipeline:
    def __init__(self, autonomy):
        self.autonomy = autonomy
        self.advanced = []
        self.plans = 0
        self.error = None
        self.probe_error = None

    def probe_connectivity(self):
        if self.probe_error:
            raise self.probe_error
        return True

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

    def test_restart_waits_for_persisted_network_retry_then_resumes_same_cycle(self):
        self.seed()
        # Isolate the waiting cycle; ready-task admission has its own regression.
        self.tasks.transition("low", "blocked", "controller", summary="Outside the reconnect fixture")
        self.supervisor.tick()
        cycle = self.autonomy.next_cycle()
        waiting = self.autonomy.update_cycle(cycle["id"], phase="waiting_network",
                                             resume_phase="ci", network_retry_count=2,
                                             next_retry_at=9999999999, head_sha="a" * 40,
                                             branch="codex/test")
        self.supervisor.release_lock()
        restarted = self.make_supervisor()
        self.assertEqual(restarted.tick()["status"], "waiting_network")
        self.assertEqual(self.pipeline.advanced, [cycle["id"]])
        self.autonomy.update_cycle(waiting["id"], next_retry_at=0)
        restarted.tick()
        self.assertEqual(self.pipeline.advanced, [cycle["id"], cycle["id"]])
        self.assertEqual(self.autonomy.get_cycle(cycle["id"])["phase"], "done")

    def test_not_due_network_wait_does_not_starve_another_existing_author(self):
        waiting = self.autonomy.create_cycle("github-wait", "engineer")
        self.autonomy.update_cycle(waiting["id"], phase="waiting_network", resume_phase="ci",
                                   next_retry_at=9999999999, last_scheduled_order=0)
        author = self.autonomy.create_cycle("runnable-author", "engineer")
        self.autonomy.update_cycle(author["id"], phase="authoring", last_scheduled_order=1)
        self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced, [author["id"]])
        self.assertEqual(self.autonomy.get_cycle(waiting["id"])["phase"], "waiting_network")
        self.assertEqual(self.supervisor.tick()["status"], "waiting_network")
        self.assertEqual(self.pipeline.advanced, [author["id"]])

    def test_not_due_wait_admits_actual_ready_store_task_without_speculative_work(self):
        waiting = self.autonomy.create_cycle("github-wait", "engineer")
        self.autonomy.update_cycle(waiting["id"], phase="waiting_network", resume_phase="ci",
                                   next_retry_at=9999999999)
        self.seed()
        self.supervisor.tick()
        admitted = next(c for c in self.autonomy.list_cycles() if c["task_id"] == "high")
        self.assertEqual(self.pipeline.advanced, [admitted["id"]])
        self.assertEqual(self.pipeline.plans, 0)
        self.assertIsNone(self.tasks.get_task("OPS001"))
        self.assertEqual(self.autonomy.get_cycle(waiting["id"])["phase"], "waiting_network")

    def test_not_due_wait_ready_admission_obeys_daily_budget(self):
        waiting = self.autonomy.create_cycle("github-wait", "engineer")
        self.autonomy.update_cycle(waiting["id"], phase="waiting_network", resume_phase="ci",
                                   next_retry_at=9999999999)
        self.seed()
        self.supervisor.policy["max_daily_attempts"] = 0
        self.assertEqual(self.supervisor.tick()["status"], "budget_limited")
        self.assertEqual(len(self.autonomy.list_cycles()), 1)
        self.assertEqual(self.pipeline.advanced, [])
        self.assertEqual(self.tasks.get_task("high")["status"], "ready")
        self.assertEqual(self.pipeline.plans, 0)
        self.assertIsNone(self.tasks.get_task("OPS001"))

    def test_all_not_due_waits_without_ready_work_do_not_schedule_audit_or_planner(self):
        for number in range(3):
            finished = self.autonomy.create_cycle("completed-%s" % number, "engineer")
            self.autonomy.update_cycle(finished["id"], phase="done")
        waiting = self.autonomy.create_cycle("github-wait", "engineer")
        self.autonomy.update_cycle(waiting["id"], phase="waiting_network", resume_phase="ci",
                                   next_retry_at=9999999999)
        self.assertEqual(self.supervisor.tick()["status"], "waiting_network")
        self.assertEqual(self.pipeline.advanced, [])
        self.assertEqual(self.pipeline.plans, 0)
        self.assertIsNone(self.tasks.get_task("OPS001"))

    def test_reconnection_probe_failure_reschedules_without_advancing(self):
        self.seed()
        self.supervisor.tick()
        cycle = self.autonomy.next_cycle()
        self.autonomy.update_cycle(cycle["id"], phase="waiting_network", resume_phase="authoring",
                                  next_retry_at=0, network_retry_count=1)
        self.pipeline.probe_error = NetworkUnavailable("still offline")
        result = self.supervisor.tick()
        waiting = self.autonomy.get_cycle(cycle["id"])
        self.assertEqual(result["status"], "waiting_network")
        self.assertEqual(waiting["phase"], "waiting_network")
        self.assertEqual(waiting["resume_phase"], "authoring")
        self.assertEqual(waiting["network_retry_count"], 2)
        self.assertEqual(self.pipeline.advanced, [cycle["id"]])

    def test_reconnection_resumes_saved_cycle_after_probe_recovers(self):
        self.seed()
        self.supervisor.tick()
        cycle = self.autonomy.next_cycle()
        self.autonomy.update_cycle(cycle["id"], phase="waiting_network", resume_phase="ci",
                                   next_retry_at=0, network_retry_count=1)
        self.pipeline.probe_error = NetworkUnavailable("still offline")
        self.supervisor.tick()
        self.pipeline.probe_error = None
        self.autonomy.update_cycle(cycle["id"], next_retry_at=0)
        self.supervisor.tick()
        self.assertEqual(self.pipeline.advanced, [cycle["id"], cycle["id"]])
        self.assertEqual(self.autonomy.get_cycle(cycle["id"])["phase"], "done")

    def test_budget_exhaustion_after_network_wait_keeps_same_cycle_without_model_launch(self):
        self.seed()
        cycle = self.autonomy.create_cycle("high", "engineer")
        self.autonomy.update_cycle(cycle["id"], phase="waiting_network", resume_phase="authoring",
                                   next_retry_at=0, network_retry_count=1)
        self.pipeline.error = BudgetExceeded("Daily budget exhausted")
        result = self.supervisor.tick()
        current = self.autonomy.get_cycle(cycle["id"])
        self.assertEqual(result["status"], "budget_limited")
        self.assertEqual(current["phase"], "authoring")
        self.assertEqual(current["id"], cycle["id"])
        self.assertEqual(self.pipeline.advanced, [cycle["id"]])

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
