import concurrent.futures
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from colony.store import Store
from colony.worker import _reserve_slot, cleanup_orphan_jobs, execute_job


class ExecuteJobTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.worktree = self.root / "checkout"
        self.worktree.mkdir()
        self.path = self.root / "isolated.db"
        self.store = Store(self.path).initialize()
        self.policy = {"_database": str(self.path), "max_concurrency": 1, "allow_implementation": True,
                       "model": "gpt-6-luna", "reasoning_effort": "medium", "role": "engineer"}
        self.binary = self.root / "fake-codex"

    def script(self, body):
        self.binary.write_text("#!" + sys.executable + "\n" + body)
        self.binary.chmod(0o755)

    def run_job(self, **options):
        arguments = {"root": self.root, "worktree": self.worktree, "prompt": "Implement the scoped task",
                     "timeout": 5, "sandbox": "workspace-write", "agent_id": "test-author", "policy": self.policy}
        arguments.update(options)
        return execute_job(**arguments)

    def test_job_passes_model_reasoning_schema_and_records_real_usage(self):
        self.script("""import json, os, pathlib, sys
prompt = sys.stdin.read()
args = sys.argv[1:]
result = pathlib.Path(args[args.index('--output-last-message') + 1])
schema = pathlib.Path(args[args.index('--output-schema') + 1])
result.with_name('capture.json').write_text(json.dumps({'args': args, 'prompt': prompt,
    'schema': json.loads(schema.read_text()), 'has_gh_token': 'GH_TOKEN' in os.environ}))
result.write_text('A scoped implementation with review evidence.')
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 13, 'output_tokens': 7}}))
""")
        schema = {"type": "object", "properties": {"summary": {"type": "string"}}}
        with patch("colony.worker.shutil.which", return_value=str(self.binary)), patch.dict(os.environ, {"GH_TOKEN": "test-secret"}):
            result = self.run_job(output_schema=schema)
        capture = json.loads(Path(result["result_path"]).with_name("capture.json").read_text())
        args = capture["args"]
        self.assertEqual(args[args.index("--model") + 1], "gpt-6-luna")
        self.assertIn('model_reasoning_effort="medium"', args)
        self.assertIn("features.multi_agent=false", args)
        self.assertEqual(args[args.index("--sandbox") + 1], "workspace-write")
        self.assertEqual(capture["schema"], schema)
        self.assertEqual(capture["prompt"], "Implement the scoped task")
        self.assertFalse(capture["has_gh_token"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["usage"], {"input_tokens": 13, "output_tokens": 7})
        self.assertEqual(self.store.get_agent("test-author")["status"], "idle")
        self.assertFalse(Path(result["result_path"]).with_name("process.json").exists())
        self.assertFalse((self.root / ".colony" / "colony.db").exists())
        finished = [event for event in self.store.snapshot()["events"] if event["kind"] == "job.finished"]
        self.assertEqual(finished[0]["data"]["model"], "gpt-6-luna")

    def test_timeout_stops_process_and_clears_agent_and_concurrency_slot(self):
        self.script("import sys, time\nsys.stdin.read()\ntime.sleep(60)\n")
        started = time.monotonic()
        with patch("colony.worker.shutil.which", return_value=str(self.binary)):
            result = self.run_job(timeout=1)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(result["status"], "failed")
        self.assertIn("wall-time limit", result["summary"])
        self.assertEqual(self.store.get_agent("test-author")["status"], "idle")
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM worker_runs WHERE status='active'").fetchone()[0], 0)

    def test_concurrent_controller_job_is_rejected_before_second_launch(self):
        release = self.root / "release"
        self.script("""import pathlib, sys, time
sys.stdin.read()
output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])
release = pathlib.Path(%r)
while not release.exists():
    time.sleep(0.01)
output.write_text('Completed controlled worker')
""" % str(release))
        with patch("colony.worker.shutil.which", return_value=str(self.binary)), concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(self.run_job, agent_id="first")
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if any(event["kind"] == "job.started" for event in self.store.snapshot()["events"]):
                        break
                    time.sleep(0.01)
                else:
                    self.fail("First fake worker did not start")
                with self.assertRaisesRegex(RuntimeError, "concurrency cap"):
                    self.run_job(agent_id="second")
                self.assertEqual(self.store.get_agent("second")["status"], "idle")
                self.assertEqual(self.store.get_agent("first")["status"], "working")
            finally:
                release.touch()
            self.assertEqual(first.result(timeout=5)["status"], "completed")

    def test_invalid_authority_or_reasoning_never_launches_a_process(self):
        with patch("colony.worker.shutil.which", return_value=str(self.binary)), patch("colony.worker.subprocess.Popen") as launch:
            with self.assertRaises(PermissionError):
                self.run_job(policy=dict(self.policy, allow_implementation=False))
            with self.assertRaises(ValueError):
                self.run_job(policy=dict(self.policy, reasoning_effort="ultra"))
            launch.assert_not_called()

    def test_empty_process_start_identity_never_authorizes_group_kill(self):
        directory = self.root / ".colony" / "runs" / "old"
        directory.mkdir(parents=True)
        record = directory / "process.json"
        record.write_text(json.dumps({"pid": 123, "started": "", "output_path": "/private/old-result.txt"}))
        response = subprocess.CompletedProcess([], 0, "Wed Oct 21 12:00:00 2026 fake --output-last-message /private/old-result.txt\n", "")
        with patch("colony.worker.subprocess.run", return_value=response), patch("colony.worker.os.getpgid", return_value=123), \
                patch("colony.worker.os.killpg") as signal_group, patch("colony.worker.time.sleep"):
            cleanup_orphan_jobs(self.root)
        signal_group.assert_not_called()

    def test_dead_worker_releases_matching_slot_in_selected_database(self):
        run_id = "dead-worker"
        directory = self.root / ".colony" / "runs" / run_id
        directory.mkdir(parents=True)
        record = directory / "process.json"
        record.write_text(json.dumps({"pid": 123, "started": "Wed Oct 21 12:00:00 2026",
                                      "output_path": "/private/old-result.txt"}))
        _reserve_slot(self.path, run_id, 1, 600)
        response = subprocess.CompletedProcess([], 1, "", "")
        with patch("colony.worker.subprocess.run", return_value=response), \
                patch("colony.worker.os.killpg", side_effect=ProcessLookupError) as signal_group:
            cleanup_orphan_jobs(self.root, self.path)
        # A zero signal may check existence; recovery never signals a guessed PID.
        self.assertTrue(all(call.args[1] == 0 for call in signal_group.call_args_list))
        self.assertFalse(record.exists())
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT status FROM worker_runs WHERE id=?", (run_id,)).fetchone()[0], "finished")
        _reserve_slot(self.path, "replacement", 1, 600)
        self.assertFalse((self.root / ".colony" / "colony.db").exists())

    def test_dead_leader_with_live_or_unverifiable_group_retains_reservation(self):
        for existence_result in (None, PermissionError()):
            with self.subTest(existence_result=type(existence_result).__name__):
                run_id = "uncertain-" + type(existence_result).__name__
                directory = self.root / ".colony" / "runs" / run_id
                directory.mkdir(parents=True)
                record = directory / "process.json"
                record.write_text(json.dumps({"pid": 123, "started": "Wed Oct 21 12:00:00 2026",
                                              "output_path": "/private/old-result.txt"}))
                _reserve_slot(self.path, run_id, 2, 600)
                response = subprocess.CompletedProcess([], 1, "", "")
                with patch("colony.worker.subprocess.run", return_value=response), \
                        patch("colony.worker.os.killpg", side_effect=existence_result) as signal_group:
                    cleanup_orphan_jobs(self.root, self.path)
                self.assertTrue(all(call.args[1] == 0 for call in signal_group.call_args_list))
                self.assertTrue(record.exists())
                with sqlite3.connect(str(self.path)) as conn:
                    self.assertEqual(conn.execute("SELECT status FROM worker_runs WHERE id=?", (run_id,)).fetchone()[0], "active")


if __name__ == "__main__":
    unittest.main()
