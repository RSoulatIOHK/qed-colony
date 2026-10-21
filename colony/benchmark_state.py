"""Bounded public projection of immutable, strictly measured benchmark reports."""

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import time
from urllib.parse import urlsplit


MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_STATUS_BYTES = 64 * 1024
MAX_STATUS_AGE_SECONDS = 300
STRATEGIES = {"colony": "by colony", "simp": "by simp_all",
              "omega": "by intros; omega", "grind": "by intros; grind"}
RESULT_STATES = {"kernel_accepted", "proof_failed", "timeout", "error",
                 "disallowed_axioms", "missing_axiom_evidence"}
PRIVATE = re.compile(r"(?:^|[\s\"'(:=])/(?:Users|home|private|var/folders|tmp)/|[A-Za-z]:\\Users\\|"
                     r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})|"
                     r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def _text(value, limit=1000):
    if not isinstance(value, str) or len(value) > limit or PRIVATE.search(value):
        raise ValueError("Unsafe benchmark text")
    return value


def _hash(value, size=64):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%s}" % size, value):
        raise ValueError("Invalid benchmark source identity")
    return value


def _count(value, maximum=100000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Invalid benchmark count")
    return value


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 864000:
        raise ValueError("Invalid benchmark duration")
    return value


def _time(value):
    value = _text(value, 80)
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Benchmark timestamp requires a timezone")
    return value


def _url(value):
    if value is None:
        return None
    value = _text(value, 2000)
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid benchmark provenance URL")
    return value


def _object(value):
    if not isinstance(value, dict):
        raise ValueError("Expected benchmark object")
    return value


def _load(path, limit):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Benchmark input must be a regular file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Benchmark input exceeds its public size limit")
    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")
    return _object(json.loads(raw.decode("utf-8"), parse_constant=invalid_constant))


def _status(value):
    if value.get("schema") != "colony.live_benchmark_status.v1":
        raise ValueError("Unsupported benchmark status schema")
    state = value.get("state")
    if state not in {"running", "ready", "error", "waiting"} or type(value.get("stale")) is not bool:
        raise ValueError("Invalid benchmark status")
    clean = {"schema": value["schema"], "state": state, "stale": value["stale"]}
    for key in ("target_revision", "latest_revision"):
        if value.get(key) is not None:
            clean[key] = _hash(value[key], 40)
    for key in ("started_at", "completed_at", "observed_at"):
        if value.get(key) is not None:
            clean[key] = _time(value[key])
    if value.get("message") is not None:
        clean["message"] = _text(value["message"], 2000)
    for key in ("completed_rows", "total_rows"):
        if value.get(key) is not None:
            clean[key] = _count(value[key])
    if clean.get("completed_rows", 0) > clean.get("total_rows", 100000):
        raise ValueError("Invalid benchmark progress")
    return clean


def _check_generated_source(source, header, source_name, statement_hash, body, heartbeats):
    """Accept only the complete isolated declaration template, never a substring."""
    declaration = re.match(r"\s*theorem ([A-Za-z_][A-Za-z_0-9.]*)\b", header)
    if (not declaration or declaration[1] != source_name or not header.endswith(":=")
            or header.count(":=") != 1 or len(re.findall(r"\btheorem\b", header)) != 1
            or re.search(r"--|/-|-/|[;#]|\b(?:import|theorem|lemma|example|axiom|def|abbrev|"
                         r"opaque|constant|instance|macro|syntax|elab|set_option|namespace|section|"
                         r"end|where|by|sorry|admit|native_decide)\b", header[declaration.end():])):
        raise ValueError("Invalid isolated benchmark theorem header")
    prefix = "import Colony.Tactic\nset_option maxHeartbeats %d\n" % heartbeats
    theorem = header + " " + body + "\n"
    if not source.startswith(prefix) or source.count(theorem) != 1:
        raise ValueError("Generated source differs from the fixed tactic template")
    before, _, after = source[len(prefix):].partition(theorem)
    if not before.endswith("\n"):
        raise ValueError("Missing isolated benchmark context boundary")
    context = before[:-1].split("\n") if before != "\n" else []
    scopes, namespaces = [], []
    for command in context:
        scope = re.fullmatch(r"\s*(namespace|section) ([A-Za-z_][A-Za-z_0-9.]*)\s*", command)
        if scope:
            scopes.append(scope[2])
            if scope[1] == "namespace":
                namespaces.append(scope[2])
        elif command.strip() not in {"abbrev ℕ := Nat", "open Nat"}:
            raise ValueError("Unsupported isolated benchmark context command")
    statement = json.dumps({"context": context, "header": header}, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(statement).hexdigest() != statement_hash:
        raise ValueError("Generated theorem differs from its statement hash")
    full_name = ".".join(namespaces + [source_name])
    expected_tail = "#print axioms " + full_name + "\n" + "\n".join("end " + name for name in reversed(scopes)) + "\n"
    expected = prefix + "\n".join(context) + "\n" + theorem + expected_tail
    if source != expected or after != expected_tail:
        raise ValueError("Generated source contains extra proof steps or declarations")


def _case(value, heartbeats):
    value = _object(value)
    clean = {key: _text(value[key], 16000 if key == "header" else 250)
             for key in ("id", "source_name", "header", "kind")}
    clean["statement_sha256"] = _hash(value["statement_sha256"])
    clean["source_url"] = _url(value.get("source_url"))
    clean["source_line"] = _count(value["source_line"]) if value.get("source_line") is not None else None
    results = _object(value["results"])
    if set(results) != set(STRATEGIES):
        raise ValueError("Incomplete benchmark strategy coverage")
    clean["results"] = {}
    for strategy, body in STRATEGIES.items():
        result = _object(results[strategy])
        if result.get("status") not in RESULT_STATES or result.get("proof_body") != body:
            raise ValueError("A benchmark result violates the fixed tactic contract")
        axioms = result.get("axioms")
        if axioms is not None and (not isinstance(axioms, list) or len(axioms) > 100):
            raise ValueError("Invalid benchmark axiom evidence")
        if result["status"] == "kernel_accepted" and (axioms is None or any(item not in {"propext", "Quot.sound", "Classical.choice"} for item in axioms)):
            raise ValueError("A kernel result uses a disallowed axiom")
        source = _text(result["generated_source"], 65536)
        source_hash = _hash(result["generated_source_sha256"])
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != source_hash:
            raise ValueError("Generated benchmark source hash differs")
        _check_generated_source(source, clean["header"], clean["source_name"],
                                clean["statement_sha256"], body, heartbeats)
        clean["results"][strategy] = {
            "status": result["status"], "wall_seconds": _seconds(result["wall_seconds"]),
            "proof_body": body, "axioms": [_text(item, 200) for item in axioms] if axioms is not None else None,
            "generated_source": source, "generated_source_sha256": source_hash,
        }
    return clean


def _report(value):
    if value.get("schema") != "colony.live_benchmark.v1":
        raise ValueError("Unsupported benchmark report schema")
    suite, protocol, assurance = (_object(value[key]) for key in ("suite", "protocol", "assurance"))
    if protocol.get("imports") != ["Colony.Tactic"] or protocol.get("proof_bodies") != STRATEGIES:
        raise ValueError("Benchmark proof contract differs")
    if assurance.get("independent_replay") is not False:
        raise ValueError("Unsupported benchmark assurance")
    cases, controls = value["cases"], value["controls"]
    if not isinstance(cases, list) or not isinstance(controls, list) or not 1 <= len(cases) <= 1000 or len(controls) > 100:
        raise ValueError("Invalid benchmark case inventory")
    heartbeats = _count(protocol["max_heartbeats"], 1000000000)
    clean = {"schema": value["schema"], "run_id": _text(value["run_id"], 250),
             "source_revision": _hash(value["source_revision"], 40),
             "started_at": _time(value["started_at"]), "completed_at": _time(value["completed_at"]),
             "suite": {"id": _text(suite["id"], 250), "case_count": _count(suite["case_count"]),
                       **{key: _hash(suite[key]) for key in ("suite_sha256", "manifest_sha256", "lock_sha256")}},
             "protocol": {"imports": ["Colony.Tactic"], "proof_bodies": dict(STRATEGIES),
                          "timeout_seconds": _seconds(protocol["timeout_seconds"]),
                          "max_heartbeats": heartbeats},
             "assurance": {"label": _text(assurance["label"], 1000), "independent_replay": False},
             "cases": [_case(case, heartbeats) for case in cases],
             "controls": [_case(case, heartbeats) for case in controls]}
    if (any(case["kind"] != "positive" for case in clean["cases"])
            or any(case["kind"] not in {"nonvacuity", "negative"} for case in clean["controls"])):
        raise ValueError("Benchmark scored cases and validity controls must be separate")
    if clean["protocol"]["timeout_seconds"] <= 0 or clean["protocol"]["max_heartbeats"] <= 0:
        raise ValueError("Benchmark resource limits must be positive")
    if "scope" in suite:
        clean["suite"]["scope"] = _text(suite["scope"], 2000)
    for key in ("manual_steps", "extra_helpers"):
        if key in protocol and protocol[key] is not False:
            raise ValueError("Manual proof steps do not belong to the strict score")
    if "toolchain" in value:
        toolchain = _object(value["toolchain"])
        clean["toolchain"] = {key: _text(toolchain[key], 1500)
                              for key in ("pin", "version_output") if key in toolchain}
    for key in ("timing_note",):
        if key in value:
            clean[key] = _text(value[key], 2000)
    for key in ("source_sha256", "runtime_source_sha256"):
        if key in value:
            hashes = _object(value[key])
            if len(hashes) > 1000:
                raise ValueError("Too many benchmark input hashes")
            clean[key] = {}
            for name, digest in hashes.items():
                name = _text(name, 500)
                if name.startswith("/") or ".." in Path(name).parts or "\\" in name or ":" in name:
                    raise ValueError("Private benchmark input path")
                clean[key][name] = _hash(digest)
    for key in ("security_boundary",):
        if key in assurance:
            clean["assurance"][key] = _text(assurance[key], 2000)
    if clean["suite"]["case_count"] != len(cases):
        raise ValueError("Scored denominator differs from the measured cases")
    selection = _object(suite.get("selection", {}))
    clean["suite"]["selection"] = {}
    for key in ("kind", "policy"):
        if key in selection:
            clean["suite"]["selection"][key] = _text(selection[key], 2000)
    for key in ("count", "remaining_named_theorems", "excluded_unnamed_examples"):
        if key in selection:
            clean["suite"]["selection"][key] = _count(selection[key])
    if len({case["id"] for case in clean["cases"] + clean["controls"]}) != len(cases) + len(controls):
        raise ValueError("Duplicate benchmark case identity")
    summary = _object(value["summary"])
    if set(summary) != set(STRATEGIES):
        raise ValueError("Incomplete benchmark summary")
    clean["summary"] = {}
    for strategy in STRATEGIES:
        measured = _object(summary[strategy])
        witnesses = [case for case in clean["controls"] if case["kind"] == "nonvacuity"]
        negatives = [case for case in clean["controls"] if case["kind"] == "negative"]
        valid = bool(witnesses) and bool(negatives) and all(case["results"][strategy]["status"] == "kernel_accepted" for case in witnesses) and all(case["results"][strategy]["status"] == "proof_failed" for case in negatives)
        if type(measured.get("valid")) is not bool or measured["valid"] != valid:
            raise ValueError("Benchmark score validity differs from its controls")
        item = {key: _count(measured[key]) for key in ("total", "proof_failed", "timeouts", "errors")}
        item.update(valid=valid, proved=_count(measured["proved"]) if valid else None,
                    accepted_unvalidated=None if valid else _count(measured["accepted_unvalidated"]))
        if (not valid and measured.get("proved") is not None) or (valid and measured.get("accepted_unvalidated") is not None):
            raise ValueError("Invalid controls cannot yield a certified score")
        item["wall_seconds"] = _seconds(measured["wall_seconds"])
        results = [case["results"][strategy]["status"] for case in clean["cases"]]
        expected = {"total": len(results),
                    "proof_failed": results.count("proof_failed"), "timeouts": results.count("timeout"),
                    "errors": sum(result not in {"kernel_accepted", "proof_failed", "timeout"} for result in results)}
        accepted = item["proved"] if valid else item["accepted_unvalidated"]
        if any(item[key] != expected[key] for key in expected) or accepted != results.count("kernel_accepted"):
            raise ValueError("Benchmark summary differs from its case evidence")
        clean["summary"][strategy] = item
    valid = all(item["valid"] for item in clean["summary"].values())
    if type(value.get("valid")) is not bool or value["valid"] != valid:
        raise ValueError("Overall benchmark validity differs from its controls")
    clean["valid"] = valid
    blaster = _object(_object(value["baseline_comparability"])["blaster"])
    clean["baseline_comparability"] = {"blaster": {"state": _text(blaster["state"], 100),
                                                        "reason": _text(blaster["reason"], 2000)}}
    return clean


def read_live_benchmark(directory, now=None):
    """Return safe measured evidence, or an explicit unavailable/error state."""
    directory = Path(directory)
    fallback = {"state": "unavailable", "stale": True, "message": "No live benchmark report is recorded."}
    if directory.is_symlink():
        return {"status": dict(fallback, state="error", message="Benchmark state is unavailable."), "report": None}
    status, report = None, None
    failed = False
    for name, limit, cleaner in (("status.json", MAX_STATUS_BYTES, _status), ("latest.json", MAX_REPORT_BYTES, _report)):
        try:
            result = cleaner(_load(directory / name, limit))
            if name == "status.json":
                status = result
            else:
                report = result
        except FileNotFoundError:
            continue
        except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
            failed = True
    status = status or dict(fallback, message="Runner status is unavailable; benchmark freshness is unconfirmed.")
    if failed:
        status = dict(status, state="error", stale=True, message="Benchmark data failed public validation; unsafe or invalid fields were withheld.")
    observed = status.get("observed_at")
    if observed is None:
        status.update(stale=True, freshness_reason="Runner observation time is unavailable.")
    else:
        observed_epoch = dt.datetime.fromisoformat(observed.replace("Z", "+00:00")).timestamp()
        age = (time.time() if now is None else now) - observed_epoch
        status["observation_age_seconds"] = round(age, 3)
        if age > MAX_STATUS_AGE_SECONDS:
            status.update(stale=True, freshness_reason="The runner has not observed its target within five minutes.")
        elif age < -30:
            status.update(stale=True, freshness_reason="The runner observation is in the future; check its clock.")
    if report is None:
        status["stale"] = True
    else:
        status["stale"] = bool(status.get("stale") or status.get("state") != "ready"
                               or status.get("target_revision") != report["source_revision"]
                               or status.get("latest_revision") != report["source_revision"])
    return {"status": status, "report": report}
