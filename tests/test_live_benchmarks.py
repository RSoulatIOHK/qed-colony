"""Strict proof bodies, fair resources and truthful live-report replacement."""

import copy
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from colony import benchmark_service as live


ROOT = Path(__file__).resolve().parents[1]


class StrictBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.corpus, self.suite, self.protocol, self.hashes = live.load_suite(ROOT)
        self.case = self.corpus["cases"][0]

    def test_every_candidate_is_one_original_header_followed_by_exact_colony(self):
        for case in self.corpus["cases"] + self.corpus["controls"]:
            source = live.render_case(case, "colony")
            self.assertIn(case["header"] + " by colony\n", source)
            self.assertEqual(source.count("import "), 1)
            self.assertIn("import Colony.Tactic\n", source)
            self.assertEqual(source.count("theorem "), 1)
            self.assertNotIn("import Colony\n", source)
            self.assertNotIn("sorry", source)
            self.assertNotIn("native_decide", source)

    def test_case_or_caller_cannot_add_manual_proof_steps(self):
        with self.assertRaises(live.BenchmarkError):
            live.render_case(self.case, "colony; exact True.intro")
        case = dict(self.case, header="axiom cheat : False\ntheorem result : False :=")
        with self.assertRaises(live.BenchmarkError):
            live.render_case(case, "colony")
        case = dict(self.case, header="theorem helper : True := by trivial\ntheorem result : True :=")
        with self.assertRaises(live.BenchmarkError):
            live.render_case(case, "colony")

    def test_pinned_suite_rejects_imports_helpers_and_resource_changes(self):
        from scripts import extract_blaster_nng4 as extraction
        for mutate in (lambda c: c.update(imports=["Colony"]),
                       lambda c: c["resource_limits"].update(timeout_seconds=1),
                       lambda c: c["cases"][0]["context"].append("axiom hidden : False")):
            corpus = copy.deepcopy(self.corpus)
            mutate(corpus)
            with patch.object(extraction, "load_corpus", return_value=corpus):
                with self.assertRaises(live.BenchmarkError):
                    live.load_suite(ROOT)

    def test_all_strategies_get_identical_limits_and_original_statement(self):
        seen = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lean").mkdir()
            def runner(command, cwd, timeout, stop=None):
                seen.append((command, timeout, (cwd / command[-1]).read_text()))
                return {"status": "completed", "returncode": 0, "wall_seconds": 1,
                        "output": "'%s' does not depend on any axioms" % self.case["full_name"]}
            rows = [live.evaluate_case(root, self.case, strategy, runner) for strategy in live.TACTICS]
        self.assertEqual({item[1] for item in seen}, {20})
        self.assertEqual({tuple(item[0]) for item in seen},
                         {("lake", "env", "lean", "-DmaxHeartbeats=200000", ".colony-live-cases/StrictCase.lean")})
        self.assertTrue(all(self.case["header"] in item[2] for item in seen))
        self.assertTrue(all(row["status"] == "kernel_accepted" for row in rows))

    def test_exit_status_or_fabricated_message_is_not_kernel_evidence(self):
        def evaluate(output, returncode=0, state="completed"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "lean").mkdir()
                runner = Mock(return_value={"status": state, "returncode": returncode,
                                            "output": output, "wall_seconds": 0.1})
                return live.evaluate_case(root, self.case, "colony", runner)["status"]
        self.assertEqual(evaluate("all proofs succeeded"), "missing_axiom_evidence")
        for axiom in ("sorryAx", "Lean.ofReduceBool", "customAxiom"):
            self.assertEqual(evaluate("'%s' depends on axioms: [%s]" % (self.case["full_name"], axiom)), "disallowed_axioms")
        self.assertEqual(evaluate("unsolved goals", 1), "proof_failed")
        self.assertEqual(evaluate("unknown module Colony\nunsolved goals", 1), "error")
        self.assertEqual(evaluate("unsolved goals", None, "timeout"), "timeout")

    def test_candidate_benchmark_dispatch_and_manual_example_imports_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "lean/Colony/Tactic.lean"
            path.parent.mkdir(parents=True)
            for content in ("import Colony\n", "import Colony.Examples.Target\n",
                            'import Lean\n def target := "BlasterBenchmarks.NNG4.zero_add"\n',
                            "import Lean\naxiom cheat : False\n",
                            "import Lean\nset_option debug.skipKernelTC true\n",
                            "import Lean\nset_option skipKernelTC true\n",
                            'import Lean\ndef flags := "--disable-kernel-check"\n',
                            "import Lean\n@[simp] theorem Outside.helper : True := by trivial\n",
                            "import Lean\ndef Outside.helper : True := by trivial\n"):
                path.write_text(content)
                with self.assertRaises(live.BenchmarkError):
                    live.candidate_hashes(root)
            path.write_text("import Lean\n")
            self.assertIn("lean/Colony/Tactic.lean", live.candidate_hashes(root))

    def test_candidate_source_symlink_directory_is_not_revision_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lean").mkdir()
            (root / "external").mkdir()
            (root / "external/Tactic.lean").write_text("import Lean\n")
            (root / "lean/Colony").symlink_to(root / "external", target_is_directory=True)
            with self.assertRaises(live.BenchmarkError):
                live.candidate_hashes(root)

    def test_tampered_original_statement_cannot_be_loaded_from_pinned_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "benchmarks", root / "benchmarks")
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/extract_blaster_nng4.py", root / "scripts/extract_blaster_nng4.py")
            path = root / live.MANIFEST
            corpus = json.loads(path.read_text())
            corpus["cases"][0]["header"] = "theorem zero_add : True :="
            path.write_text(json.dumps(corpus))
            with self.assertRaises(ValueError):
                live.load_suite(root)

    @unittest.skipUnless(shutil.which("lake"), "Pinned Lean compiler not installed")
    def test_compiler_audit_rejects_term_style_proof_def_in_different_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lean = root / "lean"
            (lean / "Colony").mkdir(parents=True)
            (lean / "lean-toolchain").write_text(live.TOOLCHAIN + "\n")
            (lean / "lakefile.toml").write_text('name="colony_audit_fixture"\n[[lean_lib]]\nname="Colony"\n')
            (lean / "Colony/Tactic.lean").write_text(
                "import Lean\ndef Outside.helper (a b : Nat) : a + b = b + a := Nat.add_comm a b\n")
            modules = []
            live.candidate_hashes(root, modules)
            build = live.run_command(["lake", "build", "Colony.Tactic"], lean, 30)
            self.assertEqual(build["returncode"], 0, build["output"])
            (lean / "Audit.lean").write_text(live.render_import_audit(modules))
            observed = live.run_command(["lake", "env", "lean", "Audit.lean"], lean, 20)
            self.assertNotEqual(observed["returncode"], 0)
            self.assertIn("Imported proof-valued helper is prohibited: Outside.helper", observed["output"])

    def test_negative_timeout_is_not_a_valid_sanity_result_or_scored_win(self):
        controls = [{"kind": kind, "results": {s: {"status": status} for s in live.TACTICS}}
                    for kind, status in (("nonvacuity", "kernel_accepted"), ("negative", "timeout"))]
        self.assertFalse(live.control_summary(controls)["colony"]["sanity_pass"])
        controls[1]["results"]["colony"]["status"] = "proof_failed"
        self.assertTrue(live.control_summary(controls)["colony"]["sanity_pass"])
        self.assertEqual(live.summary([])["colony"]["proved"], 0)
        cases = [{"results": {s: {"status": "kernel_accepted", "wall_seconds": 1}
                              for s in live.TACTICS}}]
        scores = live.summary(cases, controls)
        self.assertEqual(scores["colony"]["proved"], 1)
        self.assertTrue(scores["colony"]["valid"])
        self.assertIsNone(scores["simp"]["proved"])
        self.assertFalse(scores["simp"]["valid"])
        self.assertEqual(scores["simp"]["accepted_unvalidated"], 1)

    def test_failed_refresh_preserves_previous_report_and_marks_it_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            old = {"source_revision": "a" * 40, "completed_at": "2026-10-21T12:00:00Z"}
            live.atomic_json(state / "latest.json", old)
            runner = Mock(return_value={"status": "completed", "returncode": 1, "output": "private local failure"})
            service = live.BenchmarkService(root, state, ROOT, runner)
            with self.assertRaises(live.BenchmarkError):
                service.run_once()
            self.assertEqual(live.read_json(state / "latest.json"), old)
            status = live.read_json(state / "status.json")
            self.assertTrue(status["stale"])
            self.assertIn("observed_at", status)
            self.assertEqual(status["latest_revision"], "a" * 40)
            self.assertNotIn("private", status["message"])

    def test_nonoverlap_lock_does_not_overwrite_another_runs_status(self):
        with tempfile.TemporaryDirectory() as directory:
            service = live.BenchmarkService(Path(directory), runtime_root=ROOT)
            live.atomic_json(service.state_dir / "status.json", {"state": "running", "run_id": "first"})
            with (service.state_dir / "run.lock").open("a+") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(live.RunAlreadyActive):
                    service.run_once()
            self.assertEqual(live.read_json(service.state_dir / "status.json"), {"state": "running", "run_id": "first"})

    def test_main_advance_during_measurement_is_explicitly_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revisions = iter(["a" * 40, "a" * 40, "b" * 40])
            def runner(command, cwd, timeout, stop=None):
                output = ""
                if "rev-parse" in command:
                    output = next(revisions)
                elif "worktree" in command and "add" in command:
                    Path(command[-2]).mkdir(parents=True)
                return {"status": "completed", "returncode": 0, "output": output, "wall_seconds": 0}
            service = live.BenchmarkService(root, runtime_root=ROOT, command_runner=runner)
            report = {"schema": "colony.live_benchmark.v1", "source_revision": "a" * 40,
                      "suite": self.suite, "completed_at": "2026-10-21T12:00:00Z"}
            service.evaluate = Mock(return_value=report)
            self.assertEqual(service.run_once(), report)
            status = live.read_json(service.state_dir / "status.json")
            self.assertTrue(status["stale"])
            self.assertEqual(status["target_revision"], "b" * 40)
            self.assertEqual(status["latest_revision"], "a" * 40)

    def test_subprocess_output_and_timeout_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            result = live.run_command([sys.executable, "-c", "import time; time.sleep(30)"], Path(directory), 0.1)
            self.assertEqual(result["status"], "timeout")
            result = live.run_command([sys.executable, "-c", "print('x'*400000)"], Path(directory), 5)
            self.assertEqual(result["status"], "output_limit")
            self.assertLessEqual(len(result["output"]), live.MAX_OUTPUT)


if __name__ == "__main__":
    unittest.main()
