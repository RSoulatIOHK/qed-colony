"""Strict, deterministic live comparison against a frozen proof-free corpus.

Scope: fixed tactic bodies, original locked theorem headers, identical resources,
fresh Lean processes, and honest local kernel evidence. A separate controller
process benchmarks detached public-main checkouts; no LLM or colony attempt is
used. The pinned evaluator/configuration and installed compiler are trusted.
This pilot is not an adversarial sandbox or independent proof replay.
"""

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import tempfile
import threading
import time
import uuid


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "benchmarks/blaster-nng4-v1.json"
LOCK = "benchmarks/blaster-nng4-v1.lock.json"
TOOLCHAIN = "leanprover/lean4:v4.35.0"
TACTICS = {"colony": "colony", "simp": "simp_all", "omega": "intros; omega", "grind": "intros; grind"}
AXIOMS = frozenset({"propext", "Quot.sound", "Classical.choice"})
TIMEOUT = 20
HEARTBEATS = 200000
RUN_SECONDS = 600
MAX_OUTPUT = 256 * 1024
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
PROOF_FAILURE = re.compile(r"unsolved goals|could not close this goal|omega could not prove|"
                           r"tactic ['`]omega['`] failed|['`]?grind['`]? failed|"
                           r"simp(?:_all)? made no progress|failed to synthesize[\s\S]*Decidable")
INFRA_FAILURE = re.compile(r"unknown (?:identifier|module|constant|tactic)|unexpected token|"
                           r"object file|invalid import|no such file|failed to open")


class BenchmarkError(RuntimeError):
    """A bounded operational failure with a safe public reason code."""


class RunAlreadyActive(BenchmarkError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(str(temporary), str(path))


def read_json(path):
    try:
        path = Path(path)
        if path.stat().st_size > 8 * 1024 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def run_command(command, cwd, timeout, stop=None):
    """Bound both output and wall time, terminating the complete child group."""
    environment = {key: value for key, value in os.environ.items()
                   if key in {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "ELAN_HOME"}}
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=str(cwd), stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True, env=environment)
    output = bytearray()
    status = "completed"
    try:
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            opened = True
            while opened or process.poll() is None:
                if stop is not None and stop.is_set():
                    raise BenchmarkError("stopped")
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    status = "timeout"
                    break
                for key, _ in selector.select(min(0.2, remaining)):
                    try:
                        data = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not data:
                        selector.unregister(process.stdout)
                        opened = False
                    else:
                        output.extend(data[:MAX_OUTPUT - len(output)])
                        if len(output) >= MAX_OUTPUT:
                            status = "output_limit"
                            break
                if status != "completed":
                    break
        if status == "completed":
            process.wait(timeout=max(0.1, timeout - (time.monotonic() - started)))
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        process.stdout.close()
    return {"status": status, "returncode": process.returncode,
            "output": output.decode("utf-8", errors="replace"),
            "wall_seconds": round(time.monotonic() - started, 6)}


def load_suite(runtime_root=RUNTIME_ROOT):
    # Import only from the pinned runtime, never from the measured checkout.
    from scripts.extract_blaster_nng4 import load_corpus
    runtime_root = Path(runtime_root).resolve()
    corpus = load_corpus(runtime_root / MANIFEST, root=runtime_root)
    if (corpus.get("imports") != ["Colony.Tactic"] or corpus.get("local_toolchain") != TOOLCHAIN
            or corpus.get("resource_limits") != {"timeout_seconds": TIMEOUT, "max_heartbeats": HEARTBEATS}
            or set(corpus.get("allowed_axioms", [])) != AXIOMS):
        raise BenchmarkError("unsupported_protocol")
    for case in corpus["cases"] + corpus.get("controls", []):
        if not NAME.fullmatch(case["full_name"]) or not case["header"].rstrip().endswith(":="):
            raise BenchmarkError("invalid_case_header")
        context = "\n".join(case["context"])
        if re.search(r"\b(?:theorem|lemma|example|axiom|sorry|admit|native_decide)\b", context):
            raise BenchmarkError("helper_proof_in_context")
    paths = [MANIFEST, LOCK, "scripts/extract_blaster_nng4.py", "colony/benchmark_service.py",
             "scripts/run_live_benchmarks.py"]
    paths.extend(json.loads((runtime_root / LOCK).read_text())["protected_files"])
    hashes = {name: digest((runtime_root / name).read_bytes()) for name in sorted(set(paths))}
    protocol = {"imports": ["Colony.Tactic"], "proof_bodies": {name: "by " + body for name, body in TACTICS.items()},
                "timeout_seconds": TIMEOUT, "max_heartbeats": HEARTBEATS,
                "run_timeout_seconds": RUN_SECONDS, "fresh_process_per_case": True,
                "manual_steps": False, "extra_helpers": False}
    suite_hash = digest(json.dumps({"inputs": hashes, "protocol": protocol}, sort_keys=True).encode())
    return corpus, {"id": corpus["id"], "scope": corpus["scope"], "selection": corpus["selection"],
                    "case_count": len(corpus["cases"]), "suite_sha256": suite_hash,
                    "manifest_sha256": hashes[MANIFEST], "lock_sha256": hashes[LOCK]}, protocol, hashes


def render_case(case, strategy):
    if strategy not in TACTICS:
        raise BenchmarkError("unknown_strategy")
    header = case["header"]
    if (not re.match(r"\s*theorem\s", header) or not header.rstrip().endswith(":=")
            or len(re.findall(r"\btheorem\b", header)) != 1
            or re.search(r"\b(?:sorry|admit|axiom|native_decide)\b|(?m:^\s*#)", header)):
        raise BenchmarkError("invalid_case_header")
    # No candidate-supplied script, extra theorem, helper or earlier case proof
    # can enter this source. In particular Colony's aggregate examples are absent.
    return ("import Colony.Tactic\nset_option maxHeartbeats %d\n" % HEARTBEATS +
            "\n".join(case["context"]) + "\n" + case["header"] + " by " + TACTICS[strategy] +
            "\n#print axioms " + case["full_name"] + "\n" + "\n".join(case["context_closers"]) + "\n")


def parse_axioms(output, declaration):
    name = re.escape(declaration)
    free = re.findall(r"'%s' does not depend on any axioms" % name, output)
    found = re.findall(r"'%s' depends on axioms:\s*\[([^\]]*)\]" % name, output)
    if len(free) + len(found) != 1:
        return None
    return [] if free else sorted({item.strip() for item in found[0].split(",") if item.strip()})


def evaluate_case(worktree, case, strategy, command_runner=run_command, stop=None):
    source = render_case(case, strategy)
    directory = Path(worktree) / "lean" / ".colony-live-cases"
    directory.mkdir(exist_ok=True)
    path = directory / "StrictCase.lean"
    path.write_text(source, encoding="utf-8")
    command = ["lake", "env", "lean", "-DmaxHeartbeats=%d" % HEARTBEATS,
               ".colony-live-cases/StrictCase.lean"]
    observed = command_runner(command, Path(worktree) / "lean", TIMEOUT, stop=stop)
    axioms = None
    status = "error"
    if observed["status"] == "timeout":
        status = "timeout"
    elif observed["status"] == "completed" and observed["returncode"] == 0:
        axioms = parse_axioms(observed["output"], case["full_name"])
        status = ("missing_axiom_evidence" if axioms is None else
                  "disallowed_axioms" if set(axioms) - AXIOMS else "kernel_accepted")
    elif observed["status"] == "completed":
        if PROOF_FAILURE.search(observed["output"]) and not INFRA_FAILURE.search(observed["output"]):
            status = "proof_failed"
    return {"status": status, "wall_seconds": observed["wall_seconds"], "returncode": observed["returncode"],
            "axioms": axioms, "proof_body": "by " + TACTICS[strategy], "generated_source": source,
            "generated_source_sha256": digest(source.encode()), "command": command,
            "output_sha256": digest(observed["output"].encode())}


def candidate_hashes(worktree, module_names=None):
    """Record target sources and reject direct benchmark-identity dispatch."""
    root = Path(worktree)
    lean = root / "lean"
    hashes = {}
    for path in sorted(lean.rglob("*")):
        relative = path.relative_to(lean)
        if path.is_symlink():
            raise BenchmarkError("candidate_source_symlink")
        if any(part.startswith(".") for part in relative.parts) or not path.is_file():
            continue
        if path.suffix == ".lean" or path.name in {"lean-toolchain", "lakefile.toml", "lake-manifest.json"}:
            hashes[str(path.relative_to(root))] = digest(path.read_bytes())
    pending = ["Colony.Tactic"]
    seen = set()
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        path = lean / (module.replace(".", "/") + ".lean")
        if not path.is_file() or path.is_symlink():
            raise BenchmarkError("missing_tactic_source")
        content = path.read_text(encoding="utf-8")
        if re.search(r"skipKernelTC|skip[-_]?kernel|disable[-_]?kernel|"
                     r"kernel[-_]?check\s*[:=]\s*false", content, re.IGNORECASE):
            raise BenchmarkError("kernel_check_disabling_candidate")
        code = re.sub(r"/-[\s\S]*?-/|--[^\n]*", "", content)
        if re.search(r"\b(?:theorem|lemma|example)\b|:=\s*by\b", code):
            raise BenchmarkError("manual_helper_proof_in_candidate")
        if re.search(r"\b(?:sorry|admit|axiom|native_decide|skipKernelTC)\b|"
                     r"BlasterBenchmarks|NNG4|blaster-nng4|skip[-_]?kernel|"
                     r"disable[-_]?kernel|kernel[-_]?check\s*[:=]\s*false", code, re.IGNORECASE):
            raise BenchmarkError("forbidden_candidate_proof_or_benchmark_identity")
        for imports in re.findall(r"(?m)^\s*import\s+([^\n]+)", code):
            for imported in imports.split():
                if imported == "Colony" or imported.startswith("Colony."):
                    if imported == "Colony" or imported.startswith("Colony.Examples"):
                        raise BenchmarkError("manual_example_import")
                    pending.append(imported)
                elif imported not in {"Lean", "Std"} and not imported.startswith(("Lean.", "Std.")):
                    raise BenchmarkError("unapproved_tactic_dependency")
    if module_names is not None:
        module_names.extend(sorted(seen))
    return hashes


def render_import_audit(modules):
    if not modules or any(not NAME.fullmatch(name) for name in modules):
        raise BenchmarkError("invalid_candidate_modules")
    # Compiler-generated theorem constants for inductive constructors and
    # deriving instances are allowed. Explicit theorem declarations were
    # rejected in source; proof-valued defs/opaque declarations are checked
    # by actual type and owning module, regardless of their namespace.
    return ("import Colony.Tactic\nset_option maxHeartbeats %d\nrun_meta do\n" % HEARTBEATS +
            "  let env ← Lean.getEnv\n  let candidateModules : List Lean.Name := [" +
            ", ".join("`" + name for name in modules) + "]\n" +
            "  for (name, info) in env.constants.toList do\n" +
            "    if let some idx := env.getModuleIdxFor? name then\n" +
            "      if candidateModules.contains env.header.moduleNames[idx.toNat]! then\n" +
            "        match info with\n        | .defnInfo _ | .opaqueInfo _ =>\n" +
            "          if ← Lean.Meta.isProp info.type then\n" +
            '            throwError "Imported proof-valued helper is prohibited: {name}"\n' +
            "        | _ => pure ()\n")


def summary(cases, controls=None):
    result = {}
    sanity = control_summary(controls) if controls is not None else None
    for strategy in TACTICS:
        rows = [case["results"][strategy] for case in cases]
        valid = sanity is None or sanity[strategy]["sanity_pass"]
        accepted = sum(row["status"] == "kernel_accepted" for row in rows)
        result[strategy] = {"proved": accepted if valid else None, "valid": valid,
                            "accepted_unvalidated": accepted if not valid else None,
                            "total": len(rows), "proof_failed": sum(row["status"] == "proof_failed" for row in rows),
                            "timeouts": sum(row["status"] == "timeout" for row in rows),
                            "errors": sum(row["status"] not in {"kernel_accepted", "proof_failed", "timeout"} for row in rows),
                            "wall_seconds": round(sum(row["wall_seconds"] for row in rows), 6)}
    return result


def control_summary(controls):
    result = {}
    for strategy in TACTICS:
        witnesses = [row for row in controls if row["kind"] == "nonvacuity"]
        invalid = [row for row in controls if row["kind"] == "negative"]
        positive = bool(witnesses) and all(row["results"][strategy]["status"] == "kernel_accepted" for row in witnesses)
        rejected = bool(invalid) and all(row["results"][strategy]["status"] == "proof_failed" for row in invalid)
        result[strategy] = {"nonvacuity_accepted": positive, "invalid_rejected": rejected,
                            "sanity_pass": positive and rejected}
    return result


class BenchmarkService:
    def __init__(self, root, state_dir=None, runtime_root=RUNTIME_ROOT, command_runner=run_command, stop=None):
        self.root = Path(root).resolve()
        self.state_dir = Path(state_dir or self.root / ".colony" / "benchmark").resolve()
        self.runtime_root = Path(runtime_root).resolve()
        self.command_runner = command_runner
        self.stop = stop or threading.Event()
        self._deadline = None
        self._catalog = None
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def command(self, args, cwd=None, timeout=60):
        if self._deadline is not None:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise BenchmarkError("whole_run_deadline")
            timeout = min(timeout, remaining)
        result = self.command_runner(args, cwd or self.root, timeout, stop=self.stop)
        if result["status"] != "completed" or result["returncode"]:
            raise BenchmarkError("controller_command_failed")
        return result["output"].strip()

    def _status(self, state, target=None, latest=None, **data):
        value = {"schema": "colony.live_benchmark_status.v1", "state": state,
                 "stale": state != "ready", "target_revision": target,
                 "latest_revision": (latest or {}).get("source_revision"),
                 "started_at": None, "completed_at": (latest or {}).get("completed_at"),
                 "message": "", "completed_rows": 0, "total_rows": 0, "observed_at": now()}
        value.update(data)
        atomic_json(self.state_dir / "status.json", value)
        self._northstar(value)
        return value

    def _northstar(self, status):
        """Publish only derived inventory coverage, without executing new goals."""
        from .benchmark_catalog import load_catalog, project_coverage
        try:
            if self._catalog is None:
                self._catalog = load_catalog(self.runtime_root)
            path = self.state_dir / "latest.json"
            report, report_hash = None, None
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024:
                raw = path.read_bytes()
                report = json.loads(raw.decode("utf-8"))
                report_hash = digest(raw)
            coverage = project_coverage(self._catalog, report, status, report_hash)
        except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError):
            # An unavailable protected catalog never promotes an older coverage
            # document to current status, nor prevents the existing fixed suite.
            coverage = {"schema": "colony.benchmark_northstar.v1",
                        "status": {"state": "unavailable", "stale": True,
                                   "observed_at": status["observed_at"],
                                   "message": "Pinned whole-benchmark catalog is unavailable; no coverage is claimed."}}
        atomic_json(self.state_dir / "northstar.json", coverage)

    def run_once(self, force=False):
        lock = (self.state_dir / "run.lock").open("a+")
        try:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RunAlreadyActive("another_run_is_active") from error
            return self._run_locked(force)
        finally:
            lock.close()

    def _run_locked(self, force):
        self._catalog = None
        latest = read_json(self.state_dir / "latest.json")
        revision, worktree = None, None
        started = now()
        self._deadline = time.monotonic() + RUN_SECONDS
        try:
            corpus, suite, protocol, runtime_hashes = load_suite(self.runtime_root)
            self.command(["git", "-c", "core.hooksPath=/dev/null", "fetch", "--no-tags", "origin",
                          "refs/heads/main:refs/remotes/origin/main"])
            revision = self.command(["git", "rev-parse", "refs/remotes/origin/main"])
            if not SHA.fullmatch(revision):
                raise BenchmarkError("invalid_main_revision")
            if (not force and latest and latest.get("source_revision") == revision and
                    latest.get("suite", {}).get("suite_sha256") == suite["suite_sha256"]):
                self._status("ready", revision, latest, stale=False, message="Latest reviewed main and pinned suite are measured")
                return latest
            total = (len(corpus["cases"]) + len(corpus.get("controls", []))) * len(TACTICS)
            self._status("running", revision, latest, started_at=started,
                         message="Measuring fixed scripts in fresh Lean processes", total_rows=total)
            run_id = uuid.uuid4().hex
            worktree = self.state_dir / "worktrees" / run_id
            worktree.parent.mkdir(exist_ok=True)
            self.command(["git", "-c", "core.hooksPath=/dev/null", "worktree", "add", "--detach", str(worktree), revision])
            if self.command(["git", "rev-parse", "HEAD"], cwd=worktree) != revision:
                raise BenchmarkError("worktree_revision_mismatch")
            report = self.evaluate(worktree, revision, corpus, suite, protocol, runtime_hashes, run_id, started)
            # Retain immutable run evidence and replace latest only after every
            # strategy/case and input-invariance check has completed.
            atomic_json(self.state_dir / "runs" / (run_id + ".json"), report)
            atomic_json(self.state_dir / "latest.json", report)
            latest = report
            # Main can advance while the fair suite runs. Its older complete
            # result remains valid evidence, but must not claim current coverage.
            self.command(["git", "-c", "core.hooksPath=/dev/null", "fetch", "--no-tags", "origin",
                          "refs/heads/main:refs/remotes/origin/main"])
            newest = self.command(["git", "rev-parse", "refs/remotes/origin/main"])
            fresh = newest == revision
            self._status("ready" if fresh else "waiting", newest, report, stale=not fresh, started_at=started,
                         message="Complete fixed-suite comparison" if fresh else "Newer main awaits measurement",
                         completed_rows=total, total_rows=total)
            return report
        except (OSError, ValueError, subprocess.SubprocessError, BenchmarkError) as error:
            reason = str(error) if isinstance(error, BenchmarkError) else type(error).__name__
            self._status("error", revision, latest, stale=True, started_at=started,
                         message="Refresh incomplete: " + reason)
            raise BenchmarkError(reason) from error
        finally:
            if worktree is not None and worktree.exists():
                try:
                    self.command_runner(["git", "-c", "core.hooksPath=/dev/null", "worktree", "remove", "--force", str(worktree)],
                                        self.root, 60, stop=None)
                except (OSError, BenchmarkError, subprocess.SubprocessError):
                    pass  # Owned worktree remains available for local cleanup.
            self._deadline = None

    def evaluate(self, worktree, revision, corpus, suite, protocol, runtime_hashes, run_id, started):
        deadline = self._deadline or time.monotonic() + RUN_SECONDS
        if (worktree / "lean/lean-toolchain").read_text().strip() != TOOLCHAIN:
            raise BenchmarkError("candidate_toolchain_incompatible")
        modules = []
        inputs = candidate_hashes(worktree, modules)
        version = self.command(["lake", "env", "lean", "--version"], cwd=worktree / "lean", timeout=30)
        if not re.search(r"version 4\.35\.0(?:,|\))", version):
            raise BenchmarkError("compiler_version_mismatch")
        self.command(["lake", "build", "Colony.Tactic"], cwd=worktree / "lean", timeout=180)
        audit_source = render_import_audit(modules)
        audit_dir = worktree / "lean/.colony-live-cases"
        audit_dir.mkdir(exist_ok=True)
        (audit_dir / "ImportAudit.lean").write_text(audit_source, encoding="utf-8")
        audit_command = ["lake", "env", "lean", "-DmaxHeartbeats=%d" % HEARTBEATS,
                         ".colony-live-cases/ImportAudit.lean"]
        self.command(audit_command, cwd=worktree / "lean", timeout=TIMEOUT)
        cases, controls = [], []
        completed = 0
        total = (len(corpus["cases"]) + len(corpus.get("controls", []))) * len(TACTICS)
        for group, destination in ((corpus["cases"], cases), (corpus.get("controls", []), controls)):
            for case in group:
                row = {key: case[key] for key in ("id", "source_name", "source_line", "header", "kind", "statement_sha256")}
                row["source_url"] = (corpus["source"]["url"] + "#L" + str(case["source_line"])) if case["source_line"] else None
                row["results"] = {}
                for strategy in TACTICS:
                    if time.monotonic() + TIMEOUT > deadline:
                        raise BenchmarkError("whole_run_deadline")
                    row["results"][strategy] = evaluate_case(worktree, case, strategy, self.command_runner, self.stop)
                    completed += 1
                    self._status("running", revision, read_json(self.state_dir / "latest.json"), started_at=started,
                                 message="Measuring fixed scripts in fresh Lean processes",
                                 completed_rows=completed, total_rows=total)
                destination.append(row)
        if inputs != candidate_hashes(worktree):
            raise BenchmarkError("candidate_sources_changed_during_run")
        if load_suite(self.runtime_root)[3] != runtime_hashes:
            raise BenchmarkError("pinned_inputs_changed_during_run")
        return {"schema": "colony.live_benchmark.v1", "run_id": run_id, "source_revision": revision,
                "started_at": started, "completed_at": now(), "suite": suite, "protocol": protocol,
                "source_sha256": inputs, "runtime_source_sha256": runtime_hashes,
                "toolchain": {"pin": TOOLCHAIN, "version_output": version},
                "commands": [["lake", "env", "lean", "--version"], ["lake", "build", "Colony.Tactic"], audit_command],
                "candidate_profile": {"modules": modules, "import_audit_source": audit_source,
                                      "import_audit_sha256": digest(audit_source.encode()),
                                      "restriction": "No explicit local theorem/example/helper proofs or proof-valued defs; compiler-generated data declarations allowed"},
                "assurance": {"label": "Lean elaboration kernel; standard axiom allowlist; no independent external replay",
                              "independent_replay": False, "allowed_axioms": sorted(AXIOMS),
                              "security_boundary": "Trusted pinned evaluator/configuration, reviewed main and compiler; no adversarial sandbox"},
                "valid": all(item["sanity_pass"] for item in control_summary(controls).values()),
                "summary": summary(cases, controls), "cases": cases, "controls": controls,
                "control_summary": control_summary(controls),
                "baseline_comparability": {"blaster": {"state": "unavailable",
                    "reason": "Upstream Lean 4.24.0 versus local 4.35.0; no matched runnable comparison or superiority claim"}},
                "timing_note": "Fresh Lean process per row, identical limits; wall time includes startup/imports; no statistical speed claim"}

    def serve(self, interval=120):
        if type(interval) is not int or not 30 <= interval <= 3600:
            raise ValueError("Benchmark interval must be 30 to 3600 seconds")
        while not self.stop.is_set():
            try:
                self.run_once()
            except (RunAlreadyActive, BenchmarkError):
                pass
            self.stop.wait(interval)
