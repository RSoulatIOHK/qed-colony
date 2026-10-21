"""Evidence and false-goal handling tests; no installed Lean needed for these."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import evaluate_lean as evaluator


class AxiomEvidenceTests(unittest.TestCase):
    def test_collects_requested_declaration_only(self):
        text = "'other' depends on axioms: [sorryAx]\n'proof' depends on axioms: [propext, Quot.sound]\n"
        self.assertEqual(evaluator.parse_axioms(text, "proof"), ["Quot.sound", "propext"])

    def test_accepts_axiom_free_and_multiline_prints(self):
        self.assertEqual(evaluator.parse_axioms("'proof' does not depend on any axioms", "proof"), [])
        self.assertEqual(evaluator.parse_axioms("'proof' depends on axioms:\n[propext,\nQuot.sound]", "proof"),
                         ["Quot.sound", "propext"])

    def test_missing_or_ambiguous_evidence_is_not_certification(self):
        self.assertIsNone(evaluator.parse_axioms("all tests passed", "proof"))
        self.assertIsNone(evaluator.parse_axioms("'other' does not depend on any axioms", "proof"))
        self.assertIsNone(evaluator.parse_axioms("'proof' depends on axioms: [propext]\n" * 2, "proof"))


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((evaluator.ROOT / "benchmarks/seed-v1.json").read_text())
        self.case = self.manifest["cases"][0]
        self.declaration = "benchmark_" + self.case["id"]

    def fake_run(self, returncode, output):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(evaluator.subprocess, "run", return_value=subprocess.CompletedProcess([], returncode, output)):
                return evaluator.evaluate_case(Path(tmp), self.manifest, self.case, "colony", "colony", 1)

    def test_exit_zero_without_evidence_fails(self):
        self.assertEqual(self.fake_run(0, "success!")["status"], "missing_axiom_evidence")

    def test_sorry_custom_axiom_and_native_reduction_are_rejected(self):
        for axiom in ["sorryAx", "unsafeLemma", "Lean.ofReduceBool"]:
            with self.subTest(axiom=axiom):
                output = f"'{self.declaration}' depends on axioms: [propext, {axiom}]"
                self.assertEqual(self.fake_run(0, output)["status"], "disallowed_axioms")

    def test_standard_axioms_are_certified_with_exact_source_hash(self):
        output = f"'{self.declaration}' depends on axioms: [propext, Quot.sound]"
        row = self.fake_run(0, output)
        _, source = evaluator.generated_source(self.manifest, self.case, "colony")
        self.assertEqual(row["status"], "certified")
        self.assertEqual(row["generated_source_sha256"], evaluator.sha256_bytes(source.encode()))

    def test_rejected_proof_and_broken_environment_are_distinct(self):
        for message in ["unsolved goals", "simp_all made no progress", "`grind` failed"]:
            self.assertEqual(self.fake_run(1, message)["status"], "proof_failed")
        self.assertEqual(self.fake_run(1, "unknown module Colony\nunsolved goals")["status"], "process_error")
        self.assertEqual(self.fake_run(1, "unexpected token")["status"], "process_error")

    def test_temporary_machine_paths_are_removed_from_report_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            def diagnostic(command, **kwargs):
                return subprocess.CompletedProcess(command, 1, f"{command[-1]}:4:2: error: unsolved goals")
            with patch.object(evaluator.subprocess, "run", side_effect=diagnostic):
                row = evaluator.evaluate_case(Path(tmp), self.manifest, self.case, "colony", "colony", 1)
        self.assertEqual(row["output"], "Challenge.lean:4:2: error: unsolved goals")
        self.assertNotIn("colony-case-", row["output"])

    def test_timeout_is_not_false_statement_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(evaluator.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 1, output=b"partial")):
                row = evaluator.evaluate_case(Path(tmp), self.manifest, self.case, "colony", "colony", 1)
        self.assertEqual(row["status"], "timeout")
        self.assertEqual(row["output"], "partial")
        self.assertIsNone(row["axioms"])

    def test_false_rejection_needs_both_attack_and_nonvacuity_proofs(self):
        rows = [{"id": c["id"], "kind": c["kind"], "strategy": "colony", "status": "proof_failed"}
                for c in self.manifest["cases"]]
        summary = evaluator.summarize(self.manifest, rows)["colony"]
        self.assertFalse(summary["negative_checks"][0]["sanity_pass"])
        required = next(c for c in self.manifest["cases"] if c["kind"] == "negative")["requires_positive"]
        for row in rows:
            if row["id"] in required:
                row["status"] = "certified"
        summary = evaluator.summarize(self.manifest, rows)["colony"]
        self.assertTrue(summary["negative_checks"][0]["sanity_pass"])
        self.assertEqual(summary["positive_certified"], len(required))
        self.assertEqual(summary["positive_total"], 8)

    def test_challenge_lock_detects_definition_and_statement_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "model.lean").write_text("def model := 1\n")
            manifest_path = root / "seed.json"
            manifest = {"protected_sources": ["model.lean"], "statement": "model = 1"}
            manifest_path.write_text(json.dumps(manifest))
            lock_path = root / "seed.lock.json"
            lock = {"schema": "colony.challenge_lock.v1",
                    "manifest_sha256": evaluator.sha256_bytes(manifest_path.read_bytes()),
                    "protected_source_sha256": evaluator.file_hashes(root, ["model.lean"])}
            lock_path.write_text(json.dumps(lock))
            evaluator.validate_challenge_lock(root, manifest_path, manifest)
            (root / "model.lean").write_text("def model := 2\n")
            with self.assertRaisesRegex(ValueError, "definitions differ"):
                evaluator.validate_challenge_lock(root, manifest_path, manifest)
            (root / "model.lean").write_text("def model := 1\n")
            manifest_path.write_text(json.dumps({**manifest, "statement": "True"}))
            with self.assertRaisesRegex(ValueError, "Manifest differs"):
                evaluator.validate_challenge_lock(root, manifest_path, manifest)

    def test_manifest_cannot_weaken_axiom_allowlist_or_omit_witnesses(self):
        for change in ["axioms", "witnesses", "identifier"]:
            manifest = copy.deepcopy(self.manifest)
            if change == "axioms":
                manifest["allowed_axioms"].append("sorryAx")
            elif change == "witnesses":
                next(c for c in manifest["cases"] if c["kind"] == "negative")["requires_positive"] = []
            else:
                manifest["cases"][0]["id"] = "bad-id"
            with self.subTest(change=change), self.assertRaises(ValueError):
                evaluator.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
