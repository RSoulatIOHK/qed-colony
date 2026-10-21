import concurrent.futures
import datetime as dt
from pathlib import Path
import tempfile
import unittest
import sqlite3

from colony.autonomy_store import AutonomyStore, BudgetExceeded, CapacityUnavailable, DuplicateAttempt


class AutonomyStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.db"
        self.now = dt.datetime(2026, 10, 21, 12, tzinfo=dt.timezone.utc).timestamp()
        self.store = AutonomyStore(self.path, clock=lambda: self.now).initialize()
        self.policy = {"max_daily_seconds": 600, "max_daily_attempts": 3, "timezone": "Europe/Paris"}

    def cycle(self, task="T1"):
        return self.store.create_cycle(task, "engineer")

    def test_cycle_creation_is_idempotent_and_context_survives_reopen(self):
        cycle = self.cycle()
        updated = self.store.update_cycle(cycle["id"], phase="publishing", branch="codex/test", head="abc")
        self.assertEqual(self.cycle()["id"], cycle["id"])
        reopened = AutonomyStore(self.path).initialize()
        self.assertEqual(reopened.next_cycle()["branch"], "codex/test")
        self.assertEqual(updated["phase"], "publishing")
        reopened.update_cycle(cycle["id"], phase="done")
        self.assertIsNone(reopened.next_cycle())
        self.assertEqual(len(reopened.list_cycles()), 1)

    def test_concurrent_reservations_cannot_overspend(self):
        cycles = [self.cycle(str(number)) for number in range(5)]
        policy = dict(self.policy, max_concurrency=5)

        def reserve(stage):
            try:
                return self.store.reserve_attempt(cycles[stage]["id"], str(stage), 300, policy)
            except BudgetExceeded:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            attempts = list(executor.map(reserve, range(5)))
        self.assertEqual(sum(item is not None for item in attempts), 2)
        budget = self.store.get_budget(self.policy)
        self.assertEqual(budget["used_seconds"], 600)
        self.assertEqual(budget["reserved_seconds"], 600)

    def test_atomic_lane_admission_does_not_record_denied_attempts(self):
        cycles = [self.cycle(str(number)) for number in range(5)]
        policy = dict(self.policy, max_concurrency=2)

        def reserve(cycle):
            try:
                return self.store.reserve_attempt(cycle["id"], "author", 100, policy)
            except CapacityUnavailable:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            attempts = list(executor.map(reserve, cycles))
        self.assertEqual(sum(item is not None for item in attempts), 2)
        budget = self.store.get_budget(policy)
        self.assertEqual(budget["active_attempts"], 2)
        self.assertEqual(len(budget["active_cycle_ids"]), 2)
        self.assertEqual(budget["concurrency_limit"], 2)
        self.assertEqual(budget["attempts"], 2)
        self.assertEqual(budget["used_seconds"], 200)

    def test_one_running_stage_per_cycle_even_with_two_lanes(self):
        cycle = self.cycle()
        policy = dict(self.policy, max_concurrency=2)
        self.store.reserve_attempt(cycle["id"], "author", 100, policy)
        for stage in ("author", "review"):
            with self.assertRaises(CapacityUnavailable):
                self.store.reserve_attempt(cycle["id"], stage, 100, policy)
        self.assertEqual(len(self.store.list_attempts()), 1)

    def test_uncertain_worker_slot_occupies_capacity_without_refunding_usage(self):
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute("CREATE TABLE worker_runs(id TEXT PRIMARY KEY,status TEXT,expires REAL)")
            conn.execute("INSERT INTO worker_runs VALUES('unknown','uncertain',0)")
        policy = dict(self.policy, max_concurrency=2)
        first, second = self.cycle("first"), self.cycle("second")
        attempt = self.store.reserve_attempt(first["id"], "author", 100, policy)
        with self.assertRaises(CapacityUnavailable):
            self.store.reserve_attempt(second["id"], "author", 100, policy)
        self.store.finish_attempt(attempt, 10, status="interrupted")
        budget = self.store.get_budget(policy)
        self.assertEqual(budget["uncertain_workers"], 1)
        self.assertEqual(budget["active_attempts"], 0)
        self.assertEqual(budget["used_seconds"], 100)

    def test_known_completion_refunds_only_unused_time_and_records_usage(self):
        cycle = self.cycle()
        attempt = self.store.reserve_attempt(cycle["id"], "author:1", 300, self.policy)
        self.store.finish_attempt(attempt, 80, {"output_tokens": 17}, status="failed")
        self.assertEqual(self.store.get_budget(self.policy)["remaining_seconds"], 520)
        self.assertEqual(self.store.list_attempts()[0]["usage"], {"output_tokens": 17})
        self.store.finish_attempt(attempt, 0)
        self.assertEqual(self.store.get_budget(self.policy)["used_seconds"], 80)
        with self.assertRaises(DuplicateAttempt):
            self.store.reserve_attempt(cycle["id"], "author:1", 100, self.policy)

    def test_restart_marks_only_running_attempts_uncertain_without_refund(self):
        running = self.cycle("running")
        publishing = self.cycle("publishing")
        self.store.update_cycle(running["id"], phase="reviewing", pr_url="https://example.invalid/pull/1")
        self.store.update_cycle(publishing["id"], phase="publishing", branch="codex/persisted")
        attempt = self.store.reserve_attempt(running["id"], "review:abc123", 300, self.policy)
        recovered = AutonomyStore(self.path, clock=lambda: self.now).initialize()
        self.assertEqual(len(recovered.reconcile_interrupted()), 1)
        self.assertEqual(recovered.get_cycle(running["id"])["phase"], "needs_review")
        self.assertEqual(recovered.get_cycle(running["id"])["pr_url"], "https://example.invalid/pull/1")
        self.assertEqual(recovered.get_cycle(publishing["id"])["phase"], "publishing")
        recovered.finish_attempt(attempt, 1)
        self.assertEqual(recovered.get_budget(self.policy)["used_seconds"], 300)
        self.assertEqual(recovered.reconcile_interrupted(), [])

    def test_attempt_cap_applies_even_to_fast_failures(self):
        cycle = self.cycle()
        for number in range(3):
            attempt = self.store.reserve_attempt(cycle["id"], str(number), 100, self.policy)
            self.store.finish_attempt(attempt, 0, status="failed")
        with self.assertRaises(BudgetExceeded):
            self.store.reserve_attempt(cycle["id"], "fourth", 100, self.policy)
        self.assertTrue(self.store.get_budget(self.policy)["exhausted"])

    def test_budget_resets_at_paris_midnight_not_host_or_utc_midnight(self):
        self.now = dt.datetime(2026, 10, 21, 21, 59, 59, tzinfo=dt.timezone.utc).timestamp()
        self.store.reserve_attempt(self.cycle()["id"], "author", 600, self.policy)
        first = self.store.get_budget(self.policy)
        self.assertEqual(first["local_date"], "2026-10-21")
        self.assertEqual(first["resets_at"], "2026-10-21T22:00:00.000Z")
        self.now += 2
        fresh = self.store.get_budget(self.policy)
        self.assertEqual(fresh["local_date"], "2026-10-22")
        self.assertEqual(fresh["remaining_seconds"], 600)
        self.assertEqual(fresh["active_attempts"], 1)
        with self.assertRaises(CapacityUnavailable):
            self.store.reserve_attempt(self.cycle("next-day")["id"], "author", 100, self.policy)

    def test_service_heartbeat_preserves_phase_and_reports_staleness(self):
        self.assertEqual(self.store.service_snapshot()["status"], "stopped")
        self.store.set_service("working", 123, "cycle", "Reviewing")
        self.now += 121
        self.assertTrue(self.store.service_snapshot()["stale"])
        self.store.heartbeat_service(999)
        self.assertTrue(self.store.service_snapshot()["stale"])
        self.store.heartbeat_service(123)
        snapshot = self.store.service_snapshot(self.policy)
        self.assertFalse(snapshot["stale"])
        self.assertEqual(snapshot["message"], "Reviewing")
        self.assertEqual(snapshot["budget"]["remaining_seconds"], 600)

    def test_invalid_and_nonfinite_limits_fail_before_reservation(self):
        cycle = self.cycle()
        for timeout in (0, -1, float("nan"), True):
            with self.assertRaises(ValueError):
                self.store.reserve_attempt(cycle["id"], "author", timeout, self.policy)
        for policy in ({"max_daily_seconds": float("inf")}, {"max_daily_attempts": 1.5},
                       {"max_concurrency": 0}, {"max_concurrency": True}):
            with self.assertRaises(ValueError):
                self.store.reserve_attempt(cycle["id"], "author", 10, policy)
        self.assertEqual(self.store.list_attempts(), [])


if __name__ == "__main__":
    unittest.main()
