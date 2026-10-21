import contextlib
import io
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock

from colony.__main__ import main
from colony.project_service import install_service, service_status, start_service, stop_service, uninstall_service
from colony.service import _paths as controller_paths


RUNNING = """gui/501/io.qed-colony.project-sync.example = {
    state = running
    pid = 12345
    resource coalition = {
        state = active
        pid = 99999
        last exit code = 88
    }
    last exit code = 0
}
"""
WAITING = """gui/501/io.qed-colony.project-sync.example = {
    state = not running
    last exit code = 1
    resource coalition = {
        state = active
        pid = 99999
    }
}
"""


class ProjectServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "repository with spaces"
        self.home = Path(temporary.name) / "home"
        (self.root / "scripts").mkdir(parents=True)
        self.script = self.root / "scripts" / "sync_github_project.py"
        self.script.write_text("# reviewed original sync\n")
        self.config = self.root / "colony.json"
        self.original_config = {"project": {"repo_url": "https://github.com/example/colony",
                                           "github_project_url": "https://github.com/users/example/projects/15"},
                                "autonomy": {"repository": "example/colony", "max_daily_seconds": 3600,
                                             "credential": "must-not-be-copied"},
                                "secret": "also-not-copied"}
        self.config.write_text(json.dumps(self.original_config))
        self.calls = []

        def run(arguments, **kwargs):
            self.calls.append(arguments)
            return subprocess.CompletedProcess(arguments, 0, RUNNING if arguments[1] == "print" else "", "")

        self.run = mock.patch("colony.project_service.subprocess.run", side_effect=run).start()
        mock.patch("colony.project_service.sys.platform", "darwin").start()
        mock.patch("colony.project_service.shutil.which", return_value="/usr/local/bin/gh").start()
        self.addCleanup(mock.patch.stopall)

    def install(self, **kwargs):
        return install_service(self.root, self.config, home=self.home,
                               path_value="/usr/local/bin:/usr/bin:/bin", **kwargs)

    def test_install_pins_only_script_and_target_without_credentials_or_authority(self):
        result = self.install()
        runtime = Path(result["runtime"])
        self.assertEqual(runtime.parent, self.root / ".colony" / "project-sync")
        self.assertEqual({path.name for path in runtime.iterdir()}, {"sync_github_project.py", "colony.json"})
        pinned = json.loads(Path(result["config"]).read_text())
        self.assertEqual(pinned, {"project": self.original_config["project"]})
        self.script.write_text("# later merge must not change deployed sync\n")
        self.config.write_text("{}")
        self.assertEqual((runtime / "sync_github_project.py").read_text(), "# reviewed original sync\n")
        self.assertEqual(json.loads(Path(result["config"]).read_text()), pinned)
        self.assertEqual(Path(result["config"]).stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / ".colony" / "colony.db").exists())
        self.assertFalse((self.root / ".colony" / "service.json").exists())

    def test_launchagent_is_periodic_separate_and_has_no_keepalive_or_token(self):
        result = self.install(port=7444, interval=180)
        with Path(result["plist"]).open("rb") as stream:
            spec = plistlib.load(stream)
        self.assertTrue(spec["RunAtLoad"])
        self.assertEqual(spec["StartInterval"], 180)
        self.assertNotIn("KeepAlive", spec)
        self.assertEqual(set(spec["EnvironmentVariables"]), {"PATH", "PYTHONUNBUFFERED"})
        self.assertIn("/usr/local/bin", spec["EnvironmentVariables"]["PATH"])
        self.assertEqual(spec["WorkingDirectory"], result["runtime"])
        self.assertEqual(spec["ProgramArguments"][1], "-I")
        self.assertIn("http://127.0.0.1:7444/api/state", spec["ProgramArguments"])
        self.assertEqual(spec["ProgramArguments"][-1], "--apply")
        self.assertNotEqual(result["label"], controller_paths(self.root, self.home)["label"])
        self.assertEqual(Path(result["plist"]).stat().st_mode & 0o777, 0o600)
        self.assertIn(str(self.root / ".colony" / "logs"), spec["StandardErrorPath"])
        self.assertNotIn("must-not-be-copied", plistlib.dumps(spec).decode())
        self.assertEqual([arguments[1] for arguments in self.calls], ["bootout", "bootstrap"])

    def test_lifecycle_uses_only_its_job_and_preserves_deployment_evidence(self):
        result = self.install()
        self.calls.clear()
        self.assertFalse(stop_service(self.root, home=self.home)["started"])
        self.assertTrue(start_service(self.root, home=self.home)["started"])
        self.assertEqual([arguments[1] for arguments in self.calls], ["bootout", "print", "kickstart"])
        self.assertTrue(all(result["label"] in arguments[-1] for arguments in self.calls))
        uninstalled = uninstall_service(self.root, home=self.home)
        self.assertTrue(uninstalled["evidence_retained"])
        self.assertFalse(Path(result["plist"]).exists())
        self.assertTrue(Path(result["runtime"]).is_dir())
        with self.assertRaises(ValueError):
            start_service(self.root, home=self.home)

    def test_start_bootstraps_unloaded_agent_without_forcing_duplicate_process(self):
        self.install()
        self.run.side_effect = lambda args, **kw: subprocess.CompletedProcess(args, 113 if args[1] == "print" else 0, "", "")
        self.calls.clear()
        self.run.reset_mock()
        start_service(self.root, home=self.home)
        actions = [call.args[0][1] for call in self.run.call_args_list]
        self.assertEqual(actions, ["print", "bootstrap"])
        self.assertTrue(all("-k" not in call.args[0] for call in self.run.call_args_list))

    def test_status_distinguishes_running_idle_failed_and_unloaded(self):
        self.install()
        running = service_status(self.root, home=self.home)
        self.assertTrue(running["running"])
        self.assertEqual((running["state"], running["pid"], running["last_exit_code"]), ("running", 12345, 0))
        self.run.side_effect = lambda args, **kw: subprocess.CompletedProcess(args, 0, WAITING, "")
        waiting = service_status(self.root, home=self.home)
        self.assertTrue(waiting["loaded"])
        self.assertFalse(waiting["running"])
        self.assertIsNone(waiting["pid"])
        self.assertEqual(waiting["last_exit_code"], 1)
        self.run.side_effect = lambda args, **kw: subprocess.CompletedProcess(args, 113, "", "not loaded")
        unloaded = service_status(self.root, home=self.home)
        self.assertTrue(unloaded["installed"])
        self.assertFalse(unloaded["loaded"])

    def test_invalid_installation_never_calls_launchctl(self):
        for kwargs in ({"port": 0}, {"port": True}, {"interval": 0}, {"interval": True},
                       {"project_url": "https://github.com.evil.test/users/example/projects/1"},
                       {"project_url": "https://user:secret@github.com/users/example/projects/1"},
                       {"project_url": "https://github.com/users/example/projects/1?token=secret"},
                       {"repository": "https://evil.test/example/repo"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.install(**kwargs)
        with mock.patch("colony.project_service.sys.platform", "linux"), self.assertRaises(ValueError):
            self.install()
        with mock.patch("colony.project_service.shutil.which", return_value=None), self.assertRaises(ValueError):
            self.install()
        self.script.unlink()
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".colony").exists())

    def test_cli_project_actions_do_not_initialize_or_touch_controller_database(self):
        for action in ("install", "start", "stop", "status", "uninstall"):
            operation = "service_status" if action == "status" else action + "_service"
            with self.subTest(action=action), mock.patch("colony.__main__.Store") as store, \
                    mock.patch("colony.project_service." + operation, return_value={"ok": True}) as call, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = main(["--config", str(self.config), "project-service", action,
                               "--port", "7444", "--interval", "180"])
                self.assertEqual(result, 0)
                store.assert_not_called()
                call.assert_called_once()
                if action == "install":
                    self.assertEqual(call.call_args.kwargs["port"], 7444)
                    self.assertEqual(call.call_args.kwargs["interval"], 180)


if __name__ == "__main__":
    unittest.main()
