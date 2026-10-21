#!/usr/bin/env python3
"""Run the fixed seed goals in fresh Lean processes and collect local evidence.

This is a reproducibility/CI pilot, not a sandbox or an adversarial checker.
Manifest, evaluator and compiler are assumed to be controlled by the operator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "colony.benchmark_run.v1"
STANDARD_AXIOMS = frozenset({"propext", "Quot.sound", "Classical.choice"})
TRUST_LABEL = "Lean elaboration kernel; standard axiom allowlist; no independent external replay"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PROOF_FAILURE = re.compile(
    r"unsolved goals|colony: the initial proof portfolio could not close this goal|"
    r"omega could not prove|tactic 'omega' failed|`?grind`? failed|tactic 'grind' failed|"
    r"simp(?:_all)? made no progress|failed to synthesize[\s\S]*Decidable"
)
INFRA_FAILURE = re.compile(
    r"unknown (?:identifier|module|constant)|unexpected token|object file|"
    r"invalid import|no such file|failed to open|unknown tactic"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hashes(root: Path, paths: list[str]) -> dict[str, str]:
    hashes = {}
    for rel in sorted(set(paths)):
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"Source path escapes repository: {rel}")
        hashes[rel] = sha256_bytes(path.read_bytes())
    return hashes


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != "colony.benchmark_manifest.v1":
        raise ValueError("Unsupported manifest schema")
    if manifest.get("toolchain") != "leanprover/lean4:v4.35.0":
        raise ValueError("This pilot evaluator requires the pinned Lean 4.35.0 toolchain")
    if set(manifest.get("allowed_axioms", [])) != STANDARD_AXIOMS:
        raise ValueError("Manifest cannot change the evaluator's standard axiom allowlist")
    ids = [case["id"] for case in manifest["cases"]]
    if len(ids) != len(set(ids)) or not all(IDENTIFIER.fullmatch(i) for i in ids):
        raise ValueError("Case IDs must be unique Lean-safe identifiers")
    by_id = {case["id"]: case for case in manifest["cases"]}
    for case in manifest["cases"]:
        if case["kind"] not in {"positive", "negative", "unsupported"}:
            raise ValueError(f"Unknown case kind: {case['kind']}")
        if case["kind"] == "negative" and not case.get("requires_positive"):
            raise ValueError("Negative cases require explicit positive witnesses")
        for required in case.get("requires_positive", []):
            if required not in by_id or by_id[required]["kind"] != "positive":
                raise ValueError(f"Invalid positive witness: {required}")


def validate_challenge_lock(root: Path, manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Catch accidental specification drift; the lock itself still requires review."""
    lock_path = manifest_path.with_suffix(".lock.json")
    lock = json.loads(lock_path.read_text())
    if lock.get("schema") != "colony.challenge_lock.v1":
        raise ValueError("Unsupported challenge lock schema")
    if lock.get("manifest_sha256") != sha256_bytes(manifest_path.read_bytes()):
        raise ValueError("Manifest differs from the reviewed challenge lock")
    current = file_hashes(root, manifest["protected_sources"])
    if lock.get("protected_source_sha256") != current:
        raise ValueError("Challenge definitions differ from the reviewed challenge lock")
    return {"lock_sha256": sha256_bytes(lock_path.read_bytes()), **lock}


def parse_axioms(output: str, declaration: str) -> list[str] | None:
    """Read exactly the requested declaration's standard `#print axioms` output."""
    name = re.escape(declaration)
    no_axioms = re.findall(rf"'{name}' does not depend on any axioms", output)
    matches = re.findall(rf"'{name}' depends on axioms:\s*\[([^\]]*)\]", output)
    if len(no_axioms) + len(matches) != 1:
        return None
    if no_axioms:
        return []
    return sorted({part.strip() for part in matches[0].split(",") if part.strip()})


def generated_source(manifest: dict[str, Any], case: dict[str, Any], tactic: str) -> tuple[str, str]:
    declaration = f"benchmark_{case['id']}"
    imports = "\n".join(f"import {name}" for name in manifest["imports"])
    opens = "\n".join(f"open {name}" for name in manifest.get("open", []))
    source = (
        f"{imports}\n{opens}\n"
        f"set_option maxHeartbeats {int(manifest['max_heartbeats'])}\n"
        f"theorem {declaration} : {case['statement']} := by\n  {tactic}\n"
        f"#print axioms {declaration}\n"
    )
    return declaration, source


def evaluate_case(
    root: Path, manifest: dict[str, Any], case: dict[str, Any], strategy: str,
    tactic: str, timeout: float,
) -> dict[str, Any]:
    declaration, source = generated_source(manifest, case, tactic)
    result: dict[str, Any] = {
        "id": case["id"], "family": case["family"], "kind": case["kind"],
        "strategy": strategy, "declaration": declaration,
        "statement_sha256": sha256_bytes(case["statement"].encode()),
        "generated_source_sha256": sha256_bytes(source.encode()),
        "timeout_seconds": timeout, "axioms": None,
    }
    with tempfile.TemporaryDirectory(prefix="colony-case-") as temporary:
        source_path = Path(temporary) / "Challenge.lean"
        source_path.write_text(source)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                ["lake", "env", "lean", str(source_path)], cwd=root / "lean",
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
            )
            output = completed.stdout
            result["returncode"] = completed.returncode
            if completed.returncode:
                result["status"] = (
                    "proof_failed" if PROOF_FAILURE.search(output) and not INFRA_FAILURE.search(output)
                    else "process_error"
                )
            else:
                axioms = parse_axioms(output, declaration)
                result["axioms"] = axioms
                if axioms is None:
                    result["status"] = "missing_axiom_evidence"
                elif set(axioms) - STANDARD_AXIOMS:
                    result["status"] = "disallowed_axioms"
                else:
                    result["status"] = "certified"
        except subprocess.TimeoutExpired as error:
            raw = error.stdout or ""
            output = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            result.update(status="timeout", returncode=None)
        result["wall_seconds"] = round(time.monotonic() - started, 6)
        result["output"] = output.replace(str(source_path), "Challenge.lean")[-16000:]
    return result


def summarize(manifest: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Do not count rejection of negative/unsupported goals as a solved theorem."""
    summaries = {}
    for strategy in sorted({row["strategy"] for row in results}):
        rows = {r["id"]: r for r in results if r["strategy"] == strategy}
        positives = [r for r in rows.values() if r["kind"] == "positive"]
        negatives = []
        for case in manifest["cases"]:
            if case["kind"] == "negative":
                rejected = rows[case["id"]]["status"] == "proof_failed"
                witnesses = all(rows[key]["status"] == "certified" for key in case["requires_positive"])
                negatives.append({"id": case["id"], "rejected": rejected,
                                  "positive_witnesses_certified": witnesses,
                                  "sanity_pass": rejected and witnesses})
        summaries[strategy] = {
            "positive_certified": sum(r["status"] == "certified" for r in positives),
            "positive_total": len(positives),
            "negative_checks": negatives,
            "unsupported_certified": sum(r["kind"] == "unsupported" and r["status"] == "certified" for r in rows.values()),
            "timeouts": sum(r["status"] == "timeout" for r in rows.values()),
            "evidence_errors": sum(r["status"] in {"process_error", "missing_axiom_evidence", "disallowed_axioms"} for r in rows.values()),
        }
    return summaries


def run(manifest_path: Path, output: Path, strategies: list[str] | None = None, no_build: bool = False) -> dict[str, Any]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    validate_manifest(manifest)
    root = ROOT
    challenge_lock = validate_challenge_lock(root, manifest_path, manifest)
    selected = strategies or list(manifest["strategies"])
    if not selected or any(name not in manifest["strategies"] for name in selected):
        raise ValueError(f"Unknown strategy; available: {', '.join(manifest['strategies'])}")
    toolchain = (root / "lean/lean-toolchain").read_text().strip()
    if toolchain != manifest["toolchain"]:
        raise ValueError("lean/lean-toolchain differs from the protected manifest")
    version = subprocess.run(["lake", "env", "lean", "--version"], cwd=root / "lean", text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=True).stdout.strip()
    if not re.search(r"version 4\.35\.0(?:,|\))", version):
        raise ValueError(f"Unexpected compiler version: {version}")
    if not no_build:
        subprocess.run(["lake", "build"], cwd=root / "lean", check=True, timeout=120)
    lean_sources = [str(p.relative_to(root)) for p in (root / "lean").rglob("*.lean") if ".lake" not in p.parts]
    source_paths = lean_sources + ["lean/lean-toolchain", "lean/lakefile.toml", "scripts/evaluate_lean.py"]
    if (root / "lean/lake-manifest.json").exists():
        source_paths.append("lean/lake-manifest.json")
    source_hashes = file_hashes(root, source_paths)
    results = []
    for strategy in selected:
        for case in manifest["cases"]:
            row = evaluate_case(root, manifest, case, strategy, manifest["strategies"][strategy],
                                float(manifest["timeout_seconds"]))
            results.append(row)
            print(f"{strategy:8} {case['id']:40} {row['status']}", file=sys.stderr, flush=True)
    if source_hashes != file_hashes(root, source_paths):
        raise ValueError("Sources changed during evaluation; rerun from a stable checkout")
    validate_challenge_lock(root, manifest_path, manifest)
    report = {
        "schema": SCHEMA, "benchmark_id": manifest["id"],
        "recorded_at": datetime.now(timezone.utc).isoformat(), "scope": manifest["scope"],
        "trust": {"label": TRUST_LABEL, "independent_replay": False,
                  "kernel_axiom_allowlist": sorted(STANDARD_AXIOMS),
                  "security_boundary": "None: this local pilot trusts its evaluator, manifest and compiler installation."},
        "toolchain": {"pin": toolchain, "version_output": version},
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "challenge_lock": challenge_lock,
        "strategies": {name: manifest["strategies"][name] for name in selected},
        "protected_source_sha256": file_hashes(root, manifest["protected_sources"]),
        "source_sha256": source_hashes,
        "results": results, "summary": summarize(manifest, results),
        "timing_note": "Fresh Lean subprocess per row; wall time includes lake startup and imports; no statistical speed claims.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "benchmarks/seed-v1.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/benchmark-results.json")
    parser.add_argument("--strategies", nargs="+", help="Choose colony, simp, omega and/or grind")
    parser.add_argument("--no-build", action="store_true", help="Use an already built Lean project")
    args = parser.parse_args()
    try:
        report = run(args.manifest.resolve(), args.output.resolve(), args.strategies, args.no_build)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Evaluation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output.resolve()), "summary": report["summary"]}, indent=2))
    # The colony pilot must certify every declared positive and reject false goals
    # with their positive witnesses. Baseline incompleteness is recorded normally.
    colony = report["summary"].get("colony")
    errors = any(s["evidence_errors"] for s in report["summary"].values())
    if errors or (colony and (colony["positive_certified"] != colony["positive_total"] or
                             not all(n["sanity_pass"] for n in colony["negative_checks"]))):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
