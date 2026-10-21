import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock

from colony.benchmark_launchd import install_service, stop_service


class BenchmarkLaunchdTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "operational"
        self.source = Path(directory.name) / "reviewed"
        self.home = Path(directory.name) / "home"
        for name in ("colony", "scripts", "benchmarks"):
            (self.source / name).mkdir(parents=True)
        (self.source / "colony" / "__init__.py").write_text("")
        (self.source / "benchmarks" / "frozen.json").write_text('{"id":"fixed"}')
        for name in ("run_live_benchmarks.py", "extract_blaster_nng4.py", "evaluate_lean.py"):
            (self.source / "scripts" / name).write_text("# reviewed evaluator\n")
        mock.patch("colony.benchmark_launchd.sys.platform", "darwin").start()
        mock.patch("colony.benchmark_launchd.shutil.which", return_value="/usr/bin/tool").start()
        self.launch = mock.patch("colony.benchmark_launchd._launchctl",
                                 return_value=subprocess.CompletedProcess([], 0, "", "")).start()
        self.addCleanup(mock.patch.stopall)

    def install(self):
        return install_service(self.root, self.source, home=self.home, path_value="/usr/bin:/bin")

    def test_pins_evaluator_and_challenge_outside_tested_checkout(self):
        result = self.install()
        runtime = Path(result["runtime"])
        (self.source / "scripts" / "extract_blaster_nng4.py").write_text("# changed later\n")
        (self.source / "benchmarks" / "frozen.json").write_text('{"id":"changed"}')
        self.assertEqual((runtime / "scripts" / "extract_blaster_nng4.py").read_text(), "# reviewed evaluator\n")
        self.assertEqual(json.loads((runtime / "benchmarks" / "frozen.json").read_text())["id"], "fixed")
        with Path(result["plist"]).open("rb") as stream:
            spec = plistlib.load(stream)
        self.assertIn("-I", spec["ProgramArguments"])
        self.assertIn(str(self.root.resolve()), spec["ProgramArguments"])
        self.assertIn(str(runtime / "scripts" / "run_live_benchmarks.py"), spec["ProgramArguments"])
        self.assertEqual(set(spec["EnvironmentVariables"]), {"PATH", "PYTHONUNBUFFERED"})
        self.assertTrue(spec["KeepAlive"])
        self.assertEqual(Path(result["plist"]).stat().st_mode & 0o777, 0o600)
        self.assertIn("benchmarks/frozen.json", result["source_sha256"])
        stop_service(self.root, home=self.home)
        self.assertTrue(runtime.exists())

    def test_rejects_missing_or_symlinked_trusted_inputs_before_launchd(self):
        source = self.source / "scripts" / "extract_blaster_nng4.py"
        source.unlink()
        with self.assertRaises(ValueError):
            self.install()
        self.launch.assert_not_called()
        source.symlink_to(self.source / "scripts" / "run_live_benchmarks.py")
        with self.assertRaises(ValueError):
            self.install()
        self.launch.assert_not_called()

    def test_rejects_symlinked_resource_directories(self):
        for name in ("scripts", "colony", "benchmarks"):
            with self.subTest(name=name):
                directory = self.source / name
                moved = self.source / (name + "-moved")
                directory.rename(moved)
                directory.symlink_to(moved, target_is_directory=True)
                with self.assertRaises(ValueError):
                    self.install()
                self.launch.assert_not_called()
                directory.unlink()
                moved.rename(directory)

    def test_invalid_interval_does_not_install(self):
        for interval in (0, True, 29, 3601, 86400):
            with self.assertRaises(ValueError):
                install_service(self.root, self.source, interval=interval, home=self.home)
        self.launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
