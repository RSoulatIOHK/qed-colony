import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock

from colony.service import install_service, service_status, start_service, stop_service, uninstall_service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "repository with spaces"
        self.home = Path(self.temporary.name) / "home"
        (self.root / "colony").mkdir(parents=True)
        (self.root / "colony" / "__main__.py").write_text("# pinned original\n")
        (self.root / "observatory" / "dist").mkdir(parents=True)
        (self.root / "observatory" / "dist" / "index.html").write_text("observatory")
        self.config = self.root / "colony.json"
        self.config.write_text(json.dumps({"database": ".colony/colony.db", "seed_file": "tasks/initial.json",
                                           "observatory_dir": "observatory/dist", "autonomy": {"max_daily_seconds": 3600}}))
        self.database = self.root / ".colony" / "colony.db"
        self.calls = []
        def run(arguments, **kwargs):
            self.calls.append((arguments, kwargs))
            if arguments[1] == "print":
                return subprocess.CompletedProcess(arguments, 0, stdout="state = running\n  pid = 12345\n", stderr="")
            return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")
        self.run_mock = mock.patch("colony.service.subprocess.run", side_effect=run).start()
        self.addCleanup(mock.patch.stopall)
        mock.patch("colony.service.sys.platform", "darwin").start()
        mock.patch("colony.service.shutil.which", return_value="/usr/local/bin/codex").start()

    def install(self):
        return install_service(self.root, self.config, self.database, home=self.home,
                               path_value="/usr/local/bin:/usr/bin:/bin")

    def test_install_pins_runtime_and_authority_with_private_plist(self):
        result = self.install()
        runtime = Path(result["runtime"])
        config = json.loads(Path(result["config"]).read_text())
        self.assertEqual(config["database"], str(self.database))
        self.assertEqual(config["autonomy"]["max_daily_seconds"], 3600)
        self.assertEqual(config["seed_file"], str(self.root / "tasks" / "initial.json"))
        self.assertEqual(config["observatory_dir"], str(runtime / "observatory" / "dist"))
        (self.root / "colony" / "__main__.py").write_text("# later untrusted merge\n")
        self.config.write_text('{"autonomy":{"max_daily_seconds":999999}}')
        self.assertEqual((runtime / "colony" / "__main__.py").read_text(), "# pinned original\n")
        self.assertEqual(json.loads(Path(result["config"]).read_text())["autonomy"]["max_daily_seconds"], 3600)
        with Path(result["plist"]).open("rb") as stream:
            spec = plistlib.load(stream)
        self.assertTrue(spec["KeepAlive"])
        self.assertTrue(spec["RunAtLoad"])
        self.assertEqual(set(spec["EnvironmentVariables"]), {"PATH", "PYTHONUNBUFFERED"})
        self.assertEqual(spec["WorkingDirectory"], str(runtime))
        self.assertIn(str(self.root), spec["ProgramArguments"])
        self.assertEqual(Path(result["plist"]).stat().st_mode & 0o777, 0o600)
        self.assertEqual([call[0][1] for call in self.calls], ["bootout", "bootstrap"])

    def test_stop_unloads_keepalive_then_start_kickstarts_existing_service(self):
        self.install()
        self.calls.clear()
        self.assertFalse(stop_service(self.root, home=self.home)["started"])
        self.assertEqual(self.calls[-1][0][1], "bootout")
        self.assertTrue(start_service(self.root, home=self.home)["started"])
        self.assertEqual(self.calls[-1][0][1], "kickstart")

    def test_status_uses_launchd_pid_instead_of_plist_presence(self):
        result = self.install()
        running = service_status(self.root, home=self.home)
        self.assertTrue(running["running"])
        self.assertEqual(running["pid"], 12345)
        self.run_mock.side_effect = lambda arguments, **kwargs: subprocess.CompletedProcess(arguments, 113, "", "No such process")
        stopped = service_status(self.root, home=self.home)
        self.assertTrue(stopped["installed"])
        self.assertFalse(stopped["running"])
        self.assertFalse(stopped["loaded"])
        runtime = Path(result["runtime"])
        uninstall_service(self.root, home=self.home)
        self.assertTrue(runtime.exists())
        self.assertFalse(Path(result["plist"]).exists())

    def test_invalid_port_or_missing_codex_never_runs_launchctl(self):
        with self.assertRaises(ValueError):
            install_service(self.root, self.config, self.database, port=0, home=self.home)
        with mock.patch("colony.service.shutil.which", return_value=None):
            with self.assertRaises(ValueError):
                self.install()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
