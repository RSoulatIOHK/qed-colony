"""Whole-inventory progress cannot turn unmeasured slots into proof failures."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from colony.benchmark_catalog import CATALOG, CATALOG_LOCK, load_catalog, project_coverage
from colony.benchmark_service import BenchmarkService, BenchmarkError, atomic_json, read_json

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "benchmarks/results/blaster-nng4-3b11188d.json"


class BenchmarkCatalogTests(unittest.TestCase):
    def setUp(self):
        self.bundle = load_catalog(ROOT)
        self.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        self.status = {"state": "ready", "stale": False,
                       "target_revision": self.report["source_revision"],
                       "latest_revision": self.report["source_revision"],
                       "observed_at": "2026-10-21T15:00:00+00:00"}

    def project(self, report=None, status=None):
        return project_coverage(self.bundle, report or self.report, status or self.status)

    def test_locked_inventory_has_671_slots_not_683_declarations_or_12_sample_cases(self):
        view = project_coverage(self.bundle, None, self.status)
        self.assertEqual(view["catalog"]["total_cases"], 671)
        self.assertEqual(view["catalog"]["family_count"], 12)
        self.assertEqual(view["totals"], {"total_cases": 671, "admitted_cases": 12,
                                          "unadmitted_cases": 657, "integration_blocked_cases": 2})
        self.assertEqual(view["current"]["attempted"], 0)
        self.assertEqual(view["current"]["unattempted"], 671)
        self.assertEqual(view["current"]["proof_failed"], 0)
        self.assertIsNone(view["historical"])
        self.assertEqual(len(view["issues"]), 2)
        self.assertTrue(all(item["kind"] == "upstream_harness_targets_helper" for item in view["issues"]))

    def test_current_exact_report_earns_only_12_of_671_with_659_unattempted(self):
        view = self.project()
        self.assertEqual(view["status"]["state"], "current")
        self.assertEqual(view["current"], {"attempted": 12, "certified": 12, "proof_failed": 0,
                                           "timeouts": 0, "errors": 0, "uncertified": 0, "unattempted": 659})
        self.assertIsNone(view["historical"])
        self.assertEqual(sum(family["current"]["certified"] for family in view["families"]), 12)
        nng = next(family for family in view["families"] if family["id"] == "NNG4")
        self.assertEqual(nng["total_cases"], 108)
        self.assertEqual(nng["current"]["unattempted"], 96)
        self.assertEqual(view["next_admission"]["remaining_cases"], 96)

    def test_wrong_manifest_lock_source_statement_and_name_only_earn_no_evidence(self):
        mutations = {
            "manifest": lambda r: r["suite"].update(manifest_sha256="a" * 64),
            "lock": lambda r: r["suite"].update(lock_sha256="b" * 64),
            "case name": lambda r: r["cases"][0].update(id="nng4.a_different_case"),
            "statement": lambda r: r["cases"][0].update(statement_sha256="c" * 64),
            "source file": lambda r: r["runtime_source_sha256"].update(
                {self.bundle["bindings"][0]["manifest"]["source"]["vendored_path"]: "d" * 64}),
            "upstream revision": lambda r: r["cases"][0].update(source_url=r["cases"][0]["source_url"].replace(
                "b7cc5304bde87c269bb3ba57e560304ffd9f2189", "e" * 40)),
            "name only": lambda r: r.pop("suite"),
            "duplicate case": lambda r: r["cases"][1].update(id=r["cases"][0]["id"]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                report = copy.deepcopy(self.report)
                mutate(report)
                view = self.project(report)
                self.assertEqual(view["current"]["attempted"], 0)
                self.assertEqual(view["current"]["certified"], 0)
                self.assertIsNone(view["historical"])
                self.assertFalse(view["status"]["binding_valid"])

    def test_controls_invalid_withhold_certification_without_fabricating_proof_failures(self):
        report = copy.deepcopy(self.report)
        negative = next(case for case in report["controls"] if case["kind"] == "negative")
        negative["results"]["colony"].update(status="kernel_accepted", axioms=[])
        report["summary"]["colony"].update(valid=False, proved=None, accepted_unvalidated=12)
        report["valid"] = False
        view = self.project(report)
        self.assertEqual(view["status"]["state"], "uncertified")
        self.assertFalse(view["status"]["controls_valid"])
        self.assertEqual(view["current"]["certified"], 0)
        self.assertEqual(view["current"]["uncertified"], 12)
        self.assertEqual(view["current"]["proof_failed"], 0)
        self.assertEqual(view["current"]["unattempted"], 659)

    def test_coherently_rehashed_manual_proof_and_disallowed_axiom_earn_zero_evidence(self):
        for kind in ("manual proof", "disallowed axiom"):
            with self.subTest(kind=kind):
                report = copy.deepcopy(self.report)
                row = report["cases"][0]["results"]["colony"]
                if kind == "manual proof":
                    row["generated_source"] = row["generated_source"].replace(
                        " by colony\n", " by exact True.intro\n-- by colony\n")
                    row["generated_source_sha256"] = hashlib.sha256(row["generated_source"].encode()).hexdigest()
                else:
                    row["axioms"] = ["sorryAx"]
                view = self.project(report)
                self.assertEqual(view["current"]["attempted"], 0)
                self.assertEqual(view["current"]["certified"], 0)
                self.assertIsNone(view["historical"])

    def test_stale_or_error_report_is_separate_history_never_current_progress(self):
        for changes in ({"state": "running", "stale": True, "target_revision": "b" * 40},
                        {"state": "error", "stale": True},
                        {"latest_revision": "c" * 40}):
            with self.subTest(changes=changes):
                status = dict(self.status, **changes)
                view = self.project(status=status)
                self.assertEqual(view["current"]["certified"], 0)
                self.assertEqual(view["current"]["attempted"], 0)
                self.assertEqual(view["current"]["unattempted"], 671)
                self.assertEqual(view["historical"]["counts"]["certified"], 12)
                self.assertEqual(view["historical"]["measured_revision"], self.report["source_revision"])

    def test_catalog_historical_availability_labels_never_become_measurement(self):
        bundle = copy.deepcopy(self.bundle)
        for row in bundle["canonical"]:
            row["measurement_status"] = "historical_strict_pilot_measurement_available"
        view = project_coverage(bundle, None, self.status)
        self.assertEqual(view["current"]["certified"], 0)
        self.assertEqual(view["current"]["attempted"], 0)
        self.assertIsNone(view["historical"])

    def test_service_cache_hit_publishes_byte_bound_northstar_without_new_lean_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Mock(return_value={"status": "completed", "returncode": 0,
                                        "output": self.report["source_revision"], "wall_seconds": 0})
            service = BenchmarkService(directory, runtime_root=ROOT, command_runner=runner)
            from colony.benchmark_service import load_suite
            report = copy.deepcopy(self.report)
            report["suite"]["suite_sha256"] = load_suite(ROOT)[1]["suite_sha256"]
            atomic_json(service.state_dir / "latest.json", report)
            service.run_once()
            view = read_json(service.state_dir / "northstar.json")
            self.assertEqual(view["current"]["certified"], 12)
            expected = hashlib.sha256((service.state_dir / "latest.json").read_bytes()).hexdigest()
            self.assertEqual(view["status"]["report_sha256"], expected)
            self.assertEqual(runner.call_count, 2)
            self.assertTrue(all(call.args[0][0] == "git" for call in runner.call_args_list))

    def test_refresh_error_preserves_old_report_only_as_historical_inventory_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = Mock(return_value={"status": "completed", "returncode": 1, "output": "private failure"})
            service = BenchmarkService(directory, runtime_root=ROOT, command_runner=runner)
            atomic_json(service.state_dir / "latest.json", self.report)
            with self.assertRaises(BenchmarkError):
                service.run_once()
            view = read_json(service.state_dir / "northstar.json")
            self.assertEqual(view["current"]["certified"], 0)
            self.assertEqual(view["historical"]["counts"]["certified"], 12)
            self.assertEqual(read_json(service.state_dir / "latest.json"), self.report)

    def test_missing_catalog_withholds_old_projection_without_changing_proof_status(self):
        with tempfile.TemporaryDirectory() as directory:
            service = BenchmarkService(directory, runtime_root=directory)
            atomic_json(service.state_dir / "northstar.json", {"current": {"certified": 671}})
            status = service._status("ready", self.report["source_revision"], self.report, stale=False)
            self.assertEqual(status["state"], "ready")
            view = read_json(service.state_dir / "northstar.json")
            self.assertEqual(view["status"]["state"], "unavailable")
            self.assertNotIn("current", view)

    def test_catalog_and_protected_provenance_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = json.loads((ROOT / CATALOG_LOCK).read_text())
            for name in [CATALOG, CATALOG_LOCK] + list(lock["protected_files"]):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, path)
            load_catalog(root)
            (root / "scripts/inventory_blaster.py").write_text("# changed provenance\n")
            with self.assertRaises(ValueError):
                load_catalog(root)


if __name__ == "__main__":
    unittest.main()
