"""Protected whole-benchmark inventory and an honest, proof-free coverage view.

The catalog is a north-star denominator, never executable upstream code or a
claim that unadmitted goals failed. Only an exact, independently locked pilot
binding can attach live proof evidence to canonical upstream slots.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

CATALOG = "benchmarks/blaster-full-inventory.json"
CATALOG_LOCK = "benchmarks/blaster-full-inventory.lock.json"
CATALOG_ID = "blaster-full-inventory-b7cc5304-v1"
UPSTREAM = "https://github.com/input-output-hk/Blaster-benchmarking"
UPSTREAM_REVISION = "b7cc5304bde87c269bb3ba57e560304ffd9f2189"
PUBLIC_CATALOG = "https://github.com/RSoulatIOHK/qed-colony/blob/main/" + CATALOG
TOTAL = 671
FAMILIES = 12
SHA = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
COUNTS = ("attempted", "certified", "proof_failed", "timeouts", "errors", "uncertified", "unattempted")
AXIOMS = {"propext", "Quot.sound", "Classical.choice"}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(path, limit=8 * 1024 * 1024):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ValueError("Invalid protected catalog input")
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def _protected(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError("Invalid protected catalog path")
    result = root / path
    if any(part.is_symlink() for part in (result, *result.parents) if part != root.parent):
        raise ValueError("Symlinked protected catalog input")
    return result


def load_catalog(runtime_root):
    """Validate pinned metadata and pilot correspondence without running Lean."""
    root = Path(runtime_root).resolve()
    inventory, raw = _json(_protected(root, CATALOG))
    lock, lock_raw = _json(_protected(root, CATALOG_LOCK))
    if (inventory.get("schema") != "colony.blaster_north_star_inventory.v1"
            or inventory.get("id") != CATALOG_ID
            or lock.get("schema") != "colony.blaster_north_star_inventory_lock.v1"
            or lock.get("catalog_id") != CATALOG_ID
            or lock.get("catalog") != {"path": CATALOG, "sha256": _sha(raw)}):
        raise ValueError("Catalog lock differs")
    source = inventory["source"]
    if source.get("repository") != UPSTREAM or source.get("commit") != UPSTREAM_REVISION:
        raise ValueError("Catalog upstream identity differs")
    if (lock["source"].get("repository") != UPSTREAM
            or lock["source"].get("commit") != UPSTREAM_REVISION
            or lock["source"].get("files_sha256") != _sha(json.dumps(
                inventory["files"], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))):
        raise ValueError("Catalog source lock differs")
    protected = lock["protected_files"]
    required = {"scripts/inventory_blaster.py", "benchmarks/blaster-nng4-v1.json",
                "benchmarks/blaster-nng4-v1.lock.json", "benchmarks/upstream/blaster-b7cc5304/LICENSE",
                "benchmarks/results/blaster-nng4-first-run.json"}
    if not isinstance(protected, dict) or set(protected) != required:
        raise ValueError("Catalog has no protected provenance")
    for name, expected in protected.items():
        if not isinstance(expected, str) or not SHA.fullmatch(expected):
            raise ValueError("Invalid catalog digest")
        path = _protected(root, name)
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024 or _sha(path.read_bytes()) != expected:
            raise ValueError("Protected catalog provenance differs")
    declarations = inventory["declarations"]
    families = inventory["families"]
    if (not isinstance(declarations, list) or not isinstance(families, list)
            or len(declarations) > 2000 or len(families) != FAMILIES):
        raise ValueError("Invalid catalog inventory")
    canonical = [row for row in declarations if row.get("canonical_runner_member") is True]
    identities = [row["canonical_case_id"] for row in declarations]
    family_counts = Counter(row["family"] for row in canonical)
    if (len(canonical) != TOTAL or len(identities) != len(set(identities))
            or len(family_counts) != FAMILIES
            or {row["id"]: row["canonical_case_count"] for row in families} != dict(family_counts)):
        raise ValueError("Canonical catalog denominator differs")
    if (inventory["summary"]["canonical_runner_slots"] != TOTAL
            or inventory["summary"]["families"] != FAMILIES):
        raise ValueError("Catalog summary differs")
    bindings = []
    files = {item["path"]: item for item in inventory["files"]}
    for row in canonical:
        original_file = files[row["source_path"]]
        if (row.get("source_repository") != UPSTREAM or row.get("source_commit") != UPSTREAM_REVISION
                or row.get("header_sha256") != _sha(row["header"].encode("utf-8"))
                or row["source_sha256"] != original_file["sha256"]
                or row["source_git_blob"] != original_file["git_blob"]):
            raise ValueError("Canonical case identity differs")
        mapping = row.get("pilot_mapping")
        if mapping is None:
            continue
        manifest_path = mapping["manifest_path"]
        pilot, pilot_raw = _json(_protected(root, manifest_path))
        _, pilot_lock_raw = _json(_protected(root, mapping["lock_path"]))
        if (mapping["manifest_sha256"] != _sha(pilot_raw)
                or mapping["lock_sha256"] != _sha(pilot_lock_raw)
                or mapping["corpus_id"] != pilot["id"]):
            raise ValueError("Pilot manifest binding differs")
        matches = [case for case in pilot["cases"] if case["id"] == mapping["case_id"]]
        if len(matches) != 1:
            raise ValueError("Pilot case identity is not unique")
        case = matches[0]
        src = pilot["source"]
        if (any(row[field] != case[field] for field in ("header", "context", "full_name", "source_line", "statement_sha256"))
                or mapping["statement_sha256"] != case["statement_sha256"]
                or row["source_repository"] != src["repository"] or row["source_commit"] != src["commit"]
                or row["source_path"] != src["path"] or row["source_git_blob"] != src["git_blob"]
                or row["source_sha256"] != src["sha256"]):
            raise ValueError("Pilot statement or upstream provenance differs")
        bindings.append({"case": row, "mapping": mapping, "manifest": pilot})
    if len(bindings) != 12 or len({item["mapping"]["case_id"] for item in bindings}) != 12:
        raise ValueError("Pilot coverage binding differs")
    blocked = [row for row in canonical if row.get("integration_status") == "blocked"]
    if len(blocked) != 2 or any(row.get("target_integrity") != "upstream_harness_targets_helper" for row in blocked):
        raise ValueError("Catalog target-integrity classification differs")
    return {"inventory": inventory, "canonical": canonical, "bindings": bindings,
            "identity": {"id": CATALOG_ID, "sha256": _sha(raw), "lock_sha256": _sha(lock_raw),
                         "repository": UPSTREAM, "upstream_revision": UPSTREAM_REVISION,
                         "url": PUBLIC_CATALOG, "upstream_url": source["url"],
                         "total_cases": TOTAL, "family_count": FAMILIES}}


def _empty(total):
    return {key: total if key == "unattempted" else 0 for key in COUNTS}


def _count_outcomes(total, rows, controls_valid):
    counts = _empty(total)
    counts["attempted"] = len(rows)
    counts["unattempted"] = total - len(rows)
    for row in rows:
        status = row["results"]["colony"].get("status")
        if status == "kernel_accepted":
            axioms = row["results"]["colony"].get("axioms")
            safe = isinstance(axioms, list) and not (set(axioms) - AXIOMS)
            counts["certified" if controls_valid and safe else "uncertified"] += 1
        elif status == "proof_failed":
            counts["proof_failed"] += 1
        elif status == "timeout":
            counts["timeouts"] += 1
        else:
            counts["errors"] += 1
    return counts


def _valid_controls(report):
    controls = report.get("controls", [])
    positive = [row for row in controls if row.get("kind") == "nonvacuity"]
    negative = [row for row in controls if row.get("kind") == "negative"]
    return (report.get("valid") is True and bool(positive) and bool(negative)
            and all(row.get("results", {}).get("colony", {}).get("status") == "kernel_accepted" for row in positive)
            and all(row.get("results", {}).get("colony", {}).get("status") == "proof_failed" for row in negative))


def _matched_rows(bundle, report):
    """A report name, count or historical availability marker earns no evidence."""
    if not isinstance(report, dict) or not REVISION.fullmatch(report.get("source_revision", "")):
        return []
    suite = report.get("suite", {})
    rows = report.get("cases", [])
    if len(rows) != len(bundle["bindings"]) or suite.get("case_count") != len(rows):
        return []
    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)):
        return []
    observed = {row.get("id"): row for row in rows}
    matches = []
    for binding in bundle["bindings"]:
        original, mapping, manifest = binding["case"], binding["mapping"], binding["manifest"]
        if (suite.get("id") != mapping["corpus_id"]
                or suite.get("manifest_sha256") != mapping["manifest_sha256"]
                or suite.get("lock_sha256") != mapping["lock_sha256"]):
            continue
        row = observed.get(mapping["case_id"])
        source_hash = report.get("runtime_source_sha256", {}).get(manifest["source"]["vendored_path"])
        if (not row or row.get("kind") != "positive" or row.get("header") != original["header"]
                or row.get("statement_sha256") != mapping["statement_sha256"]
                or row.get("source_line") != original["source_line"] or row.get("source_url") != original["source_url"]
                or source_hash != original["source_sha256"]
                or row.get("results", {}).get("colony", {}).get("proof_body") != "by colony"):
            continue
        matches.append((original, row))
    return matches if len(matches) == len(bundle["bindings"]) else []


def project_coverage(bundle, report, status, report_sha256=None):
    """Keep current coverage separate from older, exactly matched evidence."""
    # A metadata label and a coherent source hash are not a proof contract.
    # Reuse the independently checked full-template/axiom/control projection
    # before attaching any derived coverage to raw controller-owned JSON.
    from .benchmark_state import _report
    try:
        report = _report(report) if isinstance(report, dict) else None
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        report = None
    matched = _matched_rows(bundle, report)
    controls_valid = isinstance(report, dict) and _valid_controls(report)
    measured = report.get("source_revision") if isinstance(report, dict) else None
    target = status.get("target_revision")
    current = bool(matched and not status.get("stale", True) and status.get("state") == "ready"
                   and target == measured and status.get("latest_revision") == measured)
    state = ("uncertified" if matched and not controls_valid else "current" if current
             else "historical" if matched else "unavailable")
    all_counts = _count_outcomes(TOTAL, [row for _, row in matched], controls_valid)
    current_counts = all_counts if current else _empty(TOTAL)
    historical = None if current or not matched else {"measured_revision": measured, "counts": all_counts}
    admitted_ids = {item["case"]["canonical_case_id"] for item in bundle["bindings"]}
    blocked = [row for row in bundle["canonical"] if row.get("integration_status") == "blocked"]
    families = []
    for family in bundle["inventory"]["families"]:
        family_id, total = family["id"], family["canonical_case_count"]
        admitted = sum(row["family"] == family_id and row["canonical_case_id"] in admitted_ids for row in bundle["canonical"])
        blocked_count = sum(row["family"] == family_id for row in blocked)
        rows = [observed for original, observed in matched if original["family"] == family_id]
        counts = _count_outcomes(total, rows, controls_valid)
        families.append({"id": family_id, "label": family_id,
                         "source_url": UPSTREAM + "/tree/" + UPSTREAM_REVISION + "/" + family["source_path"],
                         "total_cases": total, "admitted_cases": admitted,
                         "unadmitted_cases": total - admitted - blocked_count,
                         "integration_blocked_cases": blocked_count,
                         "current": counts if current else _empty(total),
                         "historical": counts if historical is not None else None})
    issues = [{"canonical_case_id": row["canonical_case_id"], "family": row["family"],
               "kind": "upstream_harness_targets_helper", "source_url": row["source_url"],
               "message": "Upstream harness selects the helper %s; the final specification %s is not its target. Separate governed clarification is required." %
                          (row["source_name"], row["intended_final_specification"]["source_name"])} for row in blocked]
    return {"schema": "colony.benchmark_northstar.v1", "catalog": bundle["identity"],
            "status": {"state": state, "stale": not current, "target_revision": target,
                       "measured_revision": measured, "observed_at": status.get("observed_at") or datetime.now(timezone.utc).isoformat(),
                       "report_sha256": report_sha256, "binding_valid": bool(matched),
                       "controls_valid": controls_valid,
                       "message": "Only exactly matched measured slots earn coverage; unattempted and blocked slots are not failed proofs."},
            "totals": {"total_cases": TOTAL, "admitted_cases": len(admitted_ids),
                       "unadmitted_cases": TOTAL - len(admitted_ids) - len(blocked),
                       "integration_blocked_cases": len(blocked)},
            "current": current_counts, "historical": historical, "families": families, "issues": issues,
            "next_admission": {"family": "NNG4", "canonical_cases": 108, "admitted_cases": 12,
                               "remaining_cases": 96, "status": "governance_required",
                               "message": "Admit remaining original NNG4 statements in fixed source-order bounded shards; preserve definitions, assumptions and limits. No new theorem is scored by this catalog."}}
