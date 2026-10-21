"""Keep the independently stated seed challenge aligned with the locked manifest."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def statements(path):
    return dict(re.findall(r"^theorem (case_[A-Za-z0-9_]+) : (.+) := by$", path.read_text(), re.MULTILINE))


class SeedChallengeTests(unittest.TestCase):
    def test_challenge_and_solution_preserve_all_prescribed_positive_statements(self):
        manifest = json.loads((ROOT / "benchmarks/seed-v1.json").read_text())
        expected = {"case_" + c["id"]: c["statement"] for c in manifest["cases"] if c["kind"] == "positive"}
        self.assertEqual(statements(ROOT / "lean/Challenge.lean"), expected)
        self.assertEqual(statements(ROOT / "lean/SeedProofs.lean"), expected)
        config = json.loads((ROOT / "lean/comparator.json").read_text())
        self.assertEqual(config["challenge_module"], "Challenge")
        self.assertEqual(config["solution_module"], "SeedProofs")
        self.assertEqual(set(config["theorem_names"]), set(expected))
        self.assertEqual(len(config["theorem_names"]), len(expected))
        self.assertEqual(set(config["permitted_axioms"]), set(manifest["allowed_axioms"]))
        self.assertEqual(config["definition_names"], [])
        self.assertEqual(config["external_kernels"], {"lean4lean": ["lean4lean", "--import"]})


if __name__ == "__main__":
    unittest.main()
