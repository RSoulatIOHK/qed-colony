import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from colony.store import Store
from colony.worker import _release_slot, _reserve_slot, _stop_process, build_prompt, run_once


class WorkerTests(unittest.TestCase):
    def make_worker_repository(self, root, body, task=None, workers=None):
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "--allow-empty", "-qm", "Initial"], check=True)
        (root / "colony.json").write_text(json.dumps({"workers": workers or {"max_concurrency": 1}}))
        binary = root / "fake-codex"
        binary.write_text("#!" + sys.executable + "\n" + body)
        binary.chmod(0o755)
        store = Store(root / "state.db").initialize()
        store.seed([task or {"id": "R1", "title": "Research", "role": "researcher", "acceptance": ["Evidence"]}])
        return binary, store

    def test_prompt_preserves_requirements_and_disallows_publication(self):
        task = {"id": "R1", "title": "Investigate", "role": "researcher",
                "description": "Compare strategies", "acceptance": ["Measured evidence"]}
        prompt = build_prompt(task, "abc123", "read-only")
        self.assertIn("Measured evidence", prompt)
        self.assertIn("abc123", prompt)
        self.assertIn("Do not push", prompt)
        self.assertIn("read-only research task", prompt)

    def test_slot_limit_is_shared_and_releasable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            Store(path).initialize()
            _reserve_slot(path, "first", 1, 10)
            with self.assertRaisesRegex(RuntimeError, "concurrency cap"):
                _reserve_slot(path, "second", 1, 10)
            _release_slot(path, "first")
            _reserve_slot(path, "second", 1, 10)
            with sqlite3.connect(str(path)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM worker_runs WHERE status='active'").fetchone()[0], 1)

    def test_bad_limits_rejected_before_launch(self):
        with self.assertRaises(ValueError):
            run_once(Path("."), Path("unused.db"), timeout=0)
        with self.assertRaises(ValueError):
            run_once(Path("."), Path("unused.db"), sandbox="danger-full-access")

    def test_no_task_does_not_launch_a_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "colony.json").write_text(json.dumps({"workers": {"max_concurrency": 1}}))
            with patch("colony.worker.shutil.which", return_value="codex"), patch("colony.worker.subprocess.Popen") as process:
                result = run_once(root, root / "state.db", role="researcher")
                process.assert_not_called()
                self.assertEqual(result["status"], "idle")

    def test_success_enters_review_and_retains_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, store = self.make_worker_repository(root, """import json, pathlib, sys
sys.stdin.read()
output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])
output.write_text('A falsifiable research proposal with explicit limits.')
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 4, 'output_tokens': 8}}))
""")
            with patch("colony.worker.shutil.which", return_value=str(binary)):
                result = run_once(root, store.path, role="researcher", timeout=5)
            self.assertEqual(result["status"], "review")
            self.assertEqual(store.get_task("R1")["status"], "review")
            self.assertTrue(Path(result["result_path"]).is_file())
            self.assertEqual(result["usage"]["output_tokens"], 8)
            self.assertNotEqual(store.get_task("R1")["status"], "done")

    def test_timeout_terminates_worker_and_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, store = self.make_worker_repository(root, "import sys, time\nsys.stdin.read()\ntime.sleep(60)\n")
            with patch("colony.worker.shutil.which", return_value=str(binary)):
                result = run_once(root, store.path, role="researcher", timeout=1)
            self.assertEqual(result["status"], "failed")
            self.assertIn("wall-time limit", result["summary"])
            self.assertEqual(store.get_agent(result["agent_id"])["status"], "idle")

    def test_large_prompt_to_nonreading_worker_is_inside_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, store = self.make_worker_repository(
                root, "import time\ntime.sleep(60)\n",
                task={"id": "R1", "title": "Large task", "role": "researcher", "description": "x" * 2_000_000})
            started = time.monotonic()
            with patch("colony.worker.shutil.which", return_value=str(binary)):
                result = run_once(root, store.path, timeout=1)
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual(result["status"], "failed")
            self.assertIn("wall-time limit", result["summary"])
            self.assertEqual(store.get_task("R1")["status"], "failed")

    def test_exited_leaders_descendant_is_killed_even_when_it_ignores_term(self):
        child_code = ("import os,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                      "print(os.getpid(),flush=True); time.sleep(60)")
        parent_code = "import subprocess,sys; subprocess.Popen([sys.executable,'-c',%r])" % child_code
        process = subprocess.Popen([sys.executable, "-c", parent_code], stdout=subprocess.PIPE,
                                   start_new_session=True, bufsize=0)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "Descendant did not start")
                self.assertTrue(process.stdout.readline().strip().isdigit())
                process.wait(timeout=5)
                _stop_process(process, grace_seconds=0.1)
                self.assertTrue(selector.select(timeout=2), "Descendant retained the output pipe")
                self.assertEqual(os.read(process.stdout.fileno(), 1), b"")
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                # Darwin may retain an unsignalable group of reparented zombie
                # descendants. The assertions above already require pipe EOF.
                pass
            process.wait(timeout=5)
            process.stdout.close()

    def test_unbroken_output_is_stopped_without_an_unbounded_line_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, store = self.make_worker_repository(root, """import os, sys, time
sys.stdin.read()
while True:
    os.write(sys.stdout.fileno(), b'x' * 65536)
""")
            with patch("colony.worker.shutil.which", return_value=str(binary)), \
                    patch("colony.worker.MAX_LOG_BYTES", 256 * 1024), \
                    patch("colony.worker.MAX_EVENT_BYTES", 8192):
                result = run_once(root, store.path, timeout=5)
            self.assertEqual(result["status"], "failed")
            self.assertIn("output limit", result["summary"])
            self.assertLessEqual(Path(result["result_path"]).with_name("events.jsonl").stat().st_size, 256 * 1024)

    def test_total_output_is_capped_even_with_many_valid_short_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, store = self.make_worker_repository(root, """import os, sys
sys.stdin.read()
while True:
    os.write(sys.stdout.fileno(), b'{"type":"progress"}\\n' * 1000)
""")
            with patch("colony.worker.shutil.which", return_value=str(binary)), \
                    patch("colony.worker.MAX_LOG_BYTES", 32768):
                result = run_once(root, store.path, timeout=5)
            self.assertEqual(result["status"], "failed")
            self.assertIn("local output limit", result["summary"])
            self.assertEqual(Path(result["result_path"]).with_name("events.jsonl").stat().st_size, 32768)

    def test_final_artifact_uses_a_bounded_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, store = self.make_worker_repository(root, """import pathlib, sys
sys.stdin.read()
output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])
output.write_text('A' * 1_000_000)
""")
            original = Path.read_text

            def no_unbounded_artifact_read(path, *args, **kwargs):
                if path.name == "result.txt":
                    self.fail("Final artifact must use a bounded stream read")
                return original(path, *args, **kwargs)

            with patch("colony.worker.shutil.which", return_value=str(binary)), \
                    patch.object(Path, "read_text", no_unbounded_artifact_read), \
                    patch("colony.worker.MAX_SUMMARY_CHARS", 64):
                result = run_once(root, store.path, timeout=5)
            self.assertEqual(result["status"], "review")
            self.assertEqual(result["summary"], "A" * 64)

    def test_policy_rejects_timeout_and_sandbox_escalation_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "colony.json").write_text(json.dumps({"workers": {"max_timeout_seconds": 2}}))
            with patch("colony.worker.subprocess.Popen") as launch:
                with self.assertRaisesRegex(ValueError, "max_timeout_seconds"):
                    run_once(root, root / "state.db", timeout=3)
                with self.assertRaisesRegex(ValueError, "allowed_sandboxes"):
                    run_once(root, root / "state.db", timeout=1, sandbox="workspace-write")
                launch.assert_not_called()
            self.assertFalse((root / "state.db").exists())

    def test_explicit_policy_can_allow_implementation_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, store = self.make_worker_repository(root, """import pathlib, sys
sys.stdin.read()
pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text('Implementation ready for review')
""", workers={"max_concurrency": 1, "allowed_sandboxes": ["read-only", "workspace-write"],
              "max_timeout_seconds": 5, "lease_seconds": 300})
            with patch("colony.worker.shutil.which", return_value=str(binary)):
                result = run_once(root, store.path, timeout=5, sandbox="workspace-write")
            self.assertEqual(result["status"], "review")


if __name__ == "__main__":
    unittest.main()
