#!/usr/bin/env python3
"""Publish selected, real benchmark evidence into the local Observatory store."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from colony.__main__ import load_config
from colony.store import Store


def import_report(store, report_path):
    raw = Path(report_path).read_bytes()
    report = json.loads(raw)
    if report.get("schema") != "colony.benchmark_run.v1":
        raise ValueError("Unsupported benchmark report")
    run_key = hashlib.sha256(raw).hexdigest()
    if any(record.get("run_key") == run_key for record in store.snapshot()["benchmarks"]):
        return 0
    for row in report["results"]:
        store.record_benchmark({
            "name": row["id"].replace("_", " "),
            "case_id": row["id"], "benchmark_id": report["benchmark_id"],
            "track": row["family"], "kind": row["kind"],
            "strategy": row["strategy"], "status": row["status"],
            "assurance": "lean_kernel" if row["status"] == "certified" else "none",
            "independent_replay": report["trust"]["independent_replay"],
            "trust_label": report["trust"]["label"],
            "wall_seconds": row["wall_seconds"], "axioms": row["axioms"],
            "description": report["scope"],
            "toolchain": report["toolchain"]["pin"],
            "statement_sha256": row["statement_sha256"],
            "generated_source_sha256": row["generated_source_sha256"],
            "measured_at": report["recorded_at"], "run_key": run_key,
        })
    store.record_event("benchmark.imported", "evaluator",
                       "Imported measured seed results; scope and trust limits retained",
                       data={"benchmark_id": report["benchmark_id"], "run_key": run_key,
                             "summary": report["summary"], "toolchain": report["toolchain"]["pin"]})
    return len(report["results"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--config", default=str(ROOT / "colony.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    count = import_report(Store(config["database"]).initialize(), args.report)
    print("Imported %s measured benchmark rows" % count)


if __name__ == "__main__":
    main()
