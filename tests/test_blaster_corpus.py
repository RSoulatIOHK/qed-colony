"""The external pilot must preserve its frozen targets without importing proofs."""

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.extract_blaster_nng4 import (
    CASE_COUNT, COMMIT, CorpusError, LOCK_PATH, MANIFEST_PATH, SOURCE_GIT_BLOB,
    SOURCE_SHA256, VENDOR, extract_cases, git_blob, load_corpus, protected_paths,
)


ROOT = Path(__file__).resolve().parents[1]


class BlasterCorpusTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for relative in protected_paths() + [MANIFEST_PATH, LOCK_PATH]:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        self.manifest_path = self.root / MANIFEST_PATH
        self.lock_path = self.root / LOCK_PATH

    def load(self):
        return load_corpus(self.manifest_path, root=self.root)

    def write_changed_manifest(self, mutate, update_lock=False):
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        mutate(manifest)
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if update_lock:
            lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
            lock["manifest"]["sha256"] = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()
            self.lock_path.write_text(json.dumps(lock), encoding="utf-8")

    def test_selected_cases_are_exact_first_named_theorems_and_rest_is_disclosed(self):
        manifest = self.load()
        self.assertEqual(manifest["source"]["commit"], COMMIT)
        self.assertEqual(manifest["source"]["named_theorem_count"], 108)
        self.assertEqual(manifest["source"]["unnamed_example_count"], 9)
        self.assertEqual(manifest["selection"]["count"], CASE_COUNT)
        self.assertEqual(manifest["selection"]["remaining_named_theorems"], 96)
        self.assertEqual([case["source_name"] for case in manifest["cases"]], [
            "zero_add", "succ_add", "add_comm", "add_assoc", "add_right_comm",
            "add_right_cancel", "add_left_cancel", "add_left_eq_self", "add_right_eq_self",
            "add_right_eq_zero", "add_left_eq_zero", "mul_le_mul_right",
        ])
        source = (self.root / VENDOR / "NNG4.lean").read_bytes()
        self.assertEqual(git_blob(source), SOURCE_GIT_BLOB)
        self.assertEqual(hashlib.sha256(source).hexdigest(), SOURCE_SHA256)

    def test_contexts_preserve_original_scopes_and_only_nat_abbreviation(self):
        cases = self.load()["cases"]
        self.assertEqual(cases[0]["context"], ["namespace BlasterBenchmarks.NNG4", "abbrev ℕ := Nat",
                                              "section Addition", "open Nat"])
        self.assertEqual(cases[0]["header"], "  theorem zero_add : ∀ (n : ℕ), 0 + n = n :=")
        self.assertEqual(cases[0]["source_line"], 7)
        self.assertEqual(cases[5]["context"], ["namespace BlasterBenchmarks.NNG4", "abbrev ℕ := Nat",
                                              "section AdvAddition"])
        self.assertEqual(cases[-1]["context_closers"], ["end AdvMultiplication", "end BlasterBenchmarks.NNG4"])
        self.assertEqual(cases[-1]["full_name"], "BlasterBenchmarks.NNG4.mul_le_mul_right")

    def test_each_rendered_goal_contains_only_its_own_declaration_and_one_colony_body(self):
        manifest = self.load()
        self.assertEqual(manifest["imports"], ["Colony.Tactic"])
        self.assertEqual(manifest["proof_contract"]["candidate_body"], "by colony")
        for case in manifest["cases"] + manifest["controls"]:
            source = "\n".join(["import Colony.Tactic"] + case["context"] +
                               [case["header"] + " by colony", "#print axioms " + case["full_name"]] +
                               case["context_closers"])
            self.assertEqual(source.count("theorem "), 1)
            self.assertEqual(source.count(" by colony"), 1)
            self.assertNotIn("sorry", source)
            self.assertNotIn("admit", source)
            self.assertNotIn("import BlasterBenchmarks", source)
            self.assertNotIn("reverseAcc_bridge", source)

    def test_invalid_control_has_a_separate_nonvacuity_witness(self):
        controls = self.load()["controls"]
        self.assertEqual([case["kind"] for case in controls], ["nonvacuity", "negative"])
        self.assertIn("(0 : Nat) + 1 ≠ 0", controls[0]["header"])
        self.assertIn("∀ n : Nat, n + 1 = n", controls[1]["header"])

    def test_statement_edit_fails_the_manifest_lock(self):
        self.write_changed_manifest(lambda data: data["cases"][0].update(header="theorem weakened : True :="))
        with self.assertRaisesRegex(CorpusError, "frozen corpus lock"):
            self.load()

    def test_recomputed_manifest_hash_cannot_hide_changed_target_order_or_context(self):
        for change in (
            lambda data: data["cases"].reverse(),
            lambda data: data["cases"][0]["context"].append("axiom leaked : False"),
            lambda data: data["cases"][0].update(header="theorem weakened : True :="),
        ):
            shutil.copy2(ROOT / MANIFEST_PATH, self.manifest_path)
            shutil.copy2(ROOT / LOCK_PATH, self.lock_path)
            self.write_changed_manifest(change, update_lock=True)
            with self.assertRaisesRegex(CorpusError, "statements, context or checking policy changed"):
                self.load()

    def test_resource_import_and_selection_edits_cannot_redefine_this_corpus(self):
        for change in (
            lambda data: data["resource_limits"].update(timeout_seconds=120),
            lambda data: data["imports"].append("Colony"),
            lambda data: data["selection"].update(count=1),
        ):
            shutil.copy2(ROOT / MANIFEST_PATH, self.manifest_path)
            shutil.copy2(ROOT / LOCK_PATH, self.lock_path)
            self.write_changed_manifest(change, update_lock=True)
            with self.assertRaises(CorpusError):
                self.load()

    def test_changed_vendored_source_and_license_are_rejected(self):
        for name in ("NNG4.lean", "LICENSE"):
            path = self.root / VENDOR / name
            original = path.read_bytes()
            path.write_bytes(original + b"\nchanged\n")
            with self.assertRaisesRegex(CorpusError, "Protected corpus input"):
                self.load()
            path.write_bytes(original)

    def test_protected_inputs_cannot_be_replaced_with_symlinks(self):
        path = self.root / VENDOR / "NNG4.lean"
        path.unlink()
        path.symlink_to(ROOT / VENDOR / "NNG4.lean")
        with self.assertRaisesRegex(CorpusError, "symlinks"):
            self.load()

    def test_extraction_rejects_extra_helpers_imports_and_nonplaceholder_proofs(self):
        for source in (
            "namespace Sample\nimport Unsafe\ntheorem target : True := by sorry\n",
            "namespace Sample\naxiom leaked : False\ntheorem target : True := by sorry\n",
            "namespace Sample\ntheorem helper : True := by trivial\n",
        ):
            with self.assertRaises(CorpusError):
                extract_cases(source, count=1)


if __name__ == "__main__":
    unittest.main()
