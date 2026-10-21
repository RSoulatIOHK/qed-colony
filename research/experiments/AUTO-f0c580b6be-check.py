"""Replay the bounded arithmetic probe; run from the repository root."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = "097a4117c7f7038f8d448217d7836a0d95d41bbe"
TARGET = "theorem nat_mul_comm_regression (a b : Nat) : a * b = b * a := by colony"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(args, source=None):
    result = subprocess.run(args, cwd=ROOT / "lean", input=source, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=60)
    record = {"cwd": "lean", "command": args, "returncode": result.returncode,
              "output": result.stdout.replace(str(ROOT), "<repository>")}
    if source is not None:
        record.update(stdin=source, stdin_sha256=sha(source.encode()))
    return record


baseline = subprocess.check_output(
    ["git", "show", f"{BASE}:lean/Colony/Tactic.lean"], cwd=ROOT, text=True)
baseline_source = baseline + "\nnamespace Colony.Examples\n" + TARGET + "\nend Colony.Examples\n"
negative_source = ("import Colony.Tactic\n"
                   "theorem invalid_shifted_mul : ∀ a b : Nat, a * b = b * a + 1 := by colony\n")
checks = {
    "baseline": run(["lake", "env", "lean", "--stdin"], baseline_source),
    "positive_and_guard": run(["lake", "env", "lean", "Colony/Examples/ArithmeticRewriteProbe.lean"]),
    "invalid_direct": run(["lake", "env", "lean", "--stdin"], negative_source),
}
paths = ["lean/Colony/Tactic.lean", "lean/Colony/Examples/ArithmeticRewriteProbe.lean",
         "research/experiments/AUTO-f0c580b6be-check.py"]
report = {
    "task": "AUTO-f0c580b6be", "base_revision": BASE,
    "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "source_sha256": {p: sha((ROOT / p).read_bytes()) for p in paths},
    "version": run(["lake", "env", "lean", "--version"]),
    "rewrite_bound": "Two fixed candidates per arithmetic call; one rw application per candidate; no recursive rewriting.",
    "checks": checks,
}
failure = "colony: the initial proof portfolio could not close this goal"
assert checks["baseline"]["returncode"] == 1 and failure in checks["baseline"]["output"]
assert checks["invalid_direct"]["returncode"] == 1 and failure in checks["invalid_direct"]["output"]
assert checks["positive_and_guard"]["returncode"] == 0
assert "'Colony.Examples.nat_mul_comm_regression' does not depend on any axioms" in checks["positive_and_guard"]["output"]
output = ROOT / "research/experiments/AUTO-f0c580b6be-checks.json"
output.write_text(json.dumps(report, indent=2) + "\n")
print("All arithmetic probe expectations met; evidence: " + str(output.relative_to(ROOT)))
