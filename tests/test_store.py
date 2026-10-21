import concurrent.futures
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from colony.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "control.db"
        self.store = Store(self.path).initialize()

    def tearDown(self):
        self.temp.cleanup()

    def task(self, task_id="a", **fields):
        return dict(id=task_id, title="Task " + task_id, role="engineer", **fields)

    def register(self, agent_id="worker"):
        return self.store.register_agent(agent_id, agent_id, "engineer")

    def test_initialization_and_seeding_are_idempotent(self):
        self.assertEqual(self.store.seed([self.task()]), 1)
        self.register()
        self.store.claim("worker")
        before = self.store.snapshot()
        self.store.initialize()
        self.assertEqual(self.store.seed([dict(self.task(), title="Changed title")]), 0)
        after = self.store.snapshot()
        self.assertEqual(before["events"], after["events"])
        self.assertEqual(after["tasks"][0]["status"], "running")
        self.assertEqual(after["tasks"][0]["title"], "Task a")

    def test_parallel_claims_are_unique(self):
        self.store.seed([self.task(str(index)) for index in range(12)])
        for index in range(12):
            self.register("worker-%d" % index)
        barrier = threading.Barrier(12)

        def claim(index):
            barrier.wait()
            return Store(self.path).claim("worker-%d" % index)["id"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            claims = list(executor.map(claim, range(12)))
        self.assertEqual(len(set(claims)), 12)
        self.assertEqual(len([task for task in self.store.snapshot()["tasks"] if task["status"] == "running"]), 12)

    def test_dependency_gate_and_priority(self):
        self.store.seed([self.task("child", depends_on=["parent"], priority=100), self.task("parent"),
                         self.task("later", priority=-1)])
        self.register()
        self.assertEqual(self.store.get_task("child")["status"], "blocked")
        self.assertEqual(self.store.claim("worker")["id"], "parent")
        self.assertIsNone(self.store.claim("worker"))
        self.store.transition("parent", "done", "worker", "Checked")
        self.assertEqual(self.store.get_task("child")["status"], "ready")
        self.assertEqual(self.store.claim("worker")["id"], "child")

    def test_expired_owner_cannot_heartbeat_or_complete(self):
        self.store.seed([self.task()])
        self.register("old")
        self.register("new")
        with patch("colony.store.time.time", return_value=1000):
            self.store.claim("old", lease_seconds=10)
        with patch("colony.store.time.time", return_value=1011):
            with self.assertRaises(PermissionError):
                self.store.heartbeat("a", "old")
            with self.assertRaises(PermissionError):
                self.store.transition("a", "done", "old")
            reclaimed = self.store.claim("new")
            self.assertEqual(reclaimed["lease_owner"], "new")
            with self.assertRaises(PermissionError):
                self.store.transition("a", "failed", "old")
            self.store.heartbeat("a", "new")
            self.store.transition("a", "review", "new", "PR ready", branch="codex/a", pr_url="https://github.com/example/project/pull/1")
        kinds = [event["kind"] for event in self.store.snapshot()["events"]]
        self.assertEqual(kinds.count("lease.expired"), 1)
        self.assertEqual(self.store.get_agent("old")["status"], "idle")

    def test_review_and_explicit_blocking(self):
        self.store.seed([self.task(), self.task("manual", status="blocked")])
        self.register()
        self.store.claim("worker")
        self.store.transition("a", "review", "worker", "Needs review")
        self.store.transition("a", "done", "reviewer", "Independent check passed")
        self.assertEqual(self.store.get_task("manual")["status"], "blocked")
        with self.assertRaises(ValueError):
            self.store.transition("a", "running", "worker")

    def test_events_are_append_only_and_measurements_start_empty(self):
        self.assertEqual(self.store.snapshot()["benchmarks"], [])
        self.store.record_event("experiment.started", "worker", "Running an actual experiment", data={"command": "lake build"})
        with sqlite3.connect(str(self.path)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM events")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE events SET message='rewritten'")
        self.store.record_benchmark({"name": "measured", "elapsed_seconds": 2.3, "result": "failed"})
        snapshot = self.store.snapshot()
        self.assertEqual(snapshot["benchmarks"][0]["result"], "failed")
        json.dumps(snapshot, allow_nan=False)

    def test_role_filter_and_missing_dependency(self):
        self.store.seed([self.task("waiting", depends_on=["absent"]), self.task("ready")])
        self.register()
        self.assertIsNone(self.store.claim("worker", role="reviewer"))
        self.assertEqual(self.store.claim("worker", role="engineer")["id"], "ready")
        self.assertEqual(self.store.get_task("waiting")["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
