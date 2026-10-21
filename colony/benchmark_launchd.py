"""Install the reviewed deterministic benchmark runner independently of models."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import uuid

from .service import _launchctl, _write_json


def _paths(root, home=None):
    root = Path(root).resolve()
    label = "io.qed-colony.benchmark." + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    return {"root": root, "label": label, "domain": "gui/%s" % os.getuid(),
            "plist": Path(home or Path.home()) / "Library" / "LaunchAgents" / (label + ".plist"),
            "metadata": root / ".colony" / "benchmark" / "service.json"}


def install_service(root, source_root=None, interval=120, *, home=None,
                    python_executable=None, path_value=None):
    """Pin evaluator and challenge separately from each tested main checkout."""
    if sys.platform != "darwin":
        raise ValueError("The benchmark service currently requires macOS launchd")
    if type(interval) is not int or not 30 <= interval <= 3600:
        raise ValueError("Benchmark interval must be between 30 and 3600 seconds")
    paths = _paths(root, home)
    root = paths["root"]
    source = Path(source_root or root).resolve()
    scripts = ("run_live_benchmarks.py", "extract_blaster_nng4.py", "evaluate_lean.py", "inventory_blaster.py")
    if (source / "scripts").is_symlink():
        raise ValueError("Reviewed benchmark scripts directory must be regular")
    for name in scripts:
        path = source / "scripts" / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Reviewed benchmark script is missing or symlinked: " + name)
    for name in ("colony", "benchmarks"):
        directory = source / name
        if directory.is_symlink() or not directory.is_dir() or any(path.is_symlink() for path in directory.rglob("*")):
            raise ValueError("Reviewed benchmark sources must be regular files: " + name)
    environment_path = os.environ.get("PATH", "") if path_value is None else path_value
    for binary in ("git", "lake"):
        if not shutil.which(binary, path=environment_path):
            raise ValueError(binary + " was not found in the benchmark service PATH")
    executable = str(Path(python_executable or sys.executable).resolve())
    if not Path(executable).is_file():
        raise ValueError("Python executable does not exist")
    deployment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    runtime = root / ".colony" / "benchmark" / "runtime" / deployment_id
    (runtime / "scripts").mkdir(parents=True, mode=0o700)
    for name in scripts:
        shutil.copyfile(source / "scripts" / name, runtime / "scripts" / name)
    for name in ("colony", "benchmarks"):
        shutil.copytree(source / name, runtime / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    hashes = {str(path.relative_to(runtime)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in runtime.rglob("*") if path.is_file()}
    state_dir = root / ".colony" / "benchmark"
    logs = root / ".colony" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    spec = {
        "Label": paths["label"],
        "ProgramArguments": [executable, "-I", str(runtime / "scripts" / scripts[0]),
                             "--root", str(root), "--state-dir", str(state_dir),
                             "--interval", str(interval)],
        "WorkingDirectory": str(runtime),
        "EnvironmentVariables": {"PATH": environment_path, "PYTHONUNBUFFERED": "1"},
        "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 60,
        # Wall-time comparisons need ordinary CLI scheduling, rather than
        # launchd's Background throttling of the runner and its Lean children.
        "ExitTimeOut": 30, "ProcessType": "Standard",
        "StandardOutPath": str(logs / "benchmark.stdout.log"),
        "StandardErrorPath": str(logs / "benchmark.stderr.log"),
    }
    paths["plist"].parent.mkdir(parents=True, exist_ok=True)
    temporary = paths["plist"].with_suffix(".plist.tmp")
    with temporary.open("wb") as stream:
        plistlib.dump(spec, stream, sort_keys=True)
    temporary.chmod(0o600)
    os.replace(temporary, paths["plist"])
    metadata = {"label": paths["label"], "deployment_id": deployment_id, "runtime": str(runtime),
                "interval": interval, "state_dir": str(state_dir), "python": executable,
                "source_sha256": hashes, "plist": str(paths["plist"]),
                "installed_at": datetime.now(timezone.utc).isoformat()}
    _write_json(paths["metadata"], metadata)
    _launchctl(["bootout", paths["domain"] + "/" + paths["label"]], required=False)
    _launchctl(["bootstrap", paths["domain"], str(paths["plist"])])
    return dict(metadata, installed=True, started=True)


def start_service(root, *, home=None):
    paths = _paths(root, home)
    if not paths["metadata"].is_file() or not paths["plist"].is_file():
        raise ValueError("Benchmark service is not installed")
    target = paths["domain"] + "/" + paths["label"]
    if _launchctl(["print", target], required=False).returncode:
        _launchctl(["bootstrap", paths["domain"], str(paths["plist"])])
    else:
        _launchctl(["kickstart", target])
    return {"installed": True, "started": True, "label": paths["label"]}


def stop_service(root, *, home=None):
    paths = _paths(root, home)
    _launchctl(["bootout", paths["domain"] + "/" + paths["label"]], required=False)
    return {"installed": paths["metadata"].is_file(), "started": False, "label": paths["label"]}


def service_status(root, *, home=None):
    paths = _paths(root, home)
    metadata = json.loads(paths["metadata"].read_text()) if paths["metadata"].is_file() else {}
    result = _launchctl(["print", paths["domain"] + "/" + paths["label"]], required=False)
    pid, depth = None, 0
    for line in result.stdout.splitlines() if result.returncode == 0 else []:
        line = line.strip()
        if line == "}":
            depth = max(0, depth - 1)
        if depth == 1 and line.startswith("pid = ") and line[6:].isdigit():
            pid = int(line[6:])
        if line.endswith("= {"):
            depth += 1
    return {"installed": bool(metadata and paths["plist"].is_file()), "loaded": result.returncode == 0,
            "running": pid is not None, "pid": pid, "label": paths["label"],
            "interval": metadata.get("interval"), "deployment_id": metadata.get("deployment_id")}


def uninstall_service(root, *, home=None):
    paths = _paths(root, home)
    stop_service(root, home=home)
    for name in ("plist", "metadata"):
        paths[name].unlink(missing_ok=True)
    return {"installed": False, "started": False, "evidence_retained": True}
