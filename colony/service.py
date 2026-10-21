"""Install a user-owned, pinned controller as a macOS LaunchAgent.

Only the controller calls this module. No credential is written to launchd's
configuration, and replacing the working tree never replaces a deployed runtime.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import uuid


def _paths(root, home=None):
    root = Path(root).resolve()
    label = "io.qed-colony.autonomy." + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    return {
        "root": root,
        "label": label,
        "domain": "gui/%s" % os.getuid(),
        "plist": Path(home or Path.home()) / "Library" / "LaunchAgents" / (label + ".plist"),
        "metadata": root / ".colony" / "service.json",
    }


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _launchctl(arguments, required=True):
    result = subprocess.run(["/bin/launchctl"] + list(arguments), capture_output=True,
                            text=True, timeout=15, check=False)
    if required and result.returncode:
        raise RuntimeError("launchctl %s failed: %s" % (arguments[0], result.stderr.strip()[:1000]))
    return result


def _read_metadata(paths):
    if not paths["metadata"].is_file():
        return None
    value = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("label") != paths["label"]:
        raise ValueError("Service metadata does not belong to this checkout")
    return value


def install_service(root, config_path, db_path, port=7331, *, home=None,
                    python_executable=None, path_value=None):
    """Pin the runtime and install/start its user LaunchAgent.

    Optional home/python/path overrides support deterministic tests. The pinned
    deployment stays on disk after uninstall, preserving operational evidence.
    """
    if sys.platform != "darwin":
        raise ValueError("The persistent service currently requires macOS launchd")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Service port must be between 1 and 65535")
    paths = _paths(root, home)
    root = paths["root"]
    config_path = Path(config_path).resolve()
    db_path = Path(db_path).resolve()
    package = root / "colony"
    if not (package / "__main__.py").is_file():
        raise ValueError("The operational root does not contain the colony package")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Service configuration must be a JSON object")
    environment_path = os.environ.get("PATH", "") if path_value is None else path_value
    codex = shutil.which("codex", path=environment_path)
    if not codex:
        raise ValueError("Codex executable was not found in the service PATH")
    executable = str(Path(python_executable or sys.executable).resolve())
    if not Path(executable).is_file():
        raise ValueError("Python executable does not exist")
    # Copy code rather than symlinking the active checkout: a merged PR cannot
    # silently change the controller's publication policy or implementation.
    deployment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    runtime = root / ".colony" / "runtime" / deployment_id
    runtime.mkdir(parents=True)
    shutil.copytree(package, runtime / "colony", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    source_static = (config_path.parent / config.get("observatory_dir", "observatory/dist")).resolve()
    static = runtime / "observatory" / "dist"
    static.mkdir(parents=True)
    for name in ("index.html", "app.js", "styles.css", "state.json"):
        source = source_static / name
        if source.is_file():
            shutil.copyfile(source, static / name)
    config["database"] = str(db_path)
    config["seed_file"] = str((config_path.parent / config.get("seed_file", "tasks/initial.json")).resolve())
    config["observatory_dir"] = str(static)
    config["deployment"] = {"id": deployment_id, "operational_root": str(root), "codex_executable": str(Path(codex).resolve())}
    pinned_config = runtime / "colony.json"
    _write_json(pinned_config, config)
    logs = root / ".colony" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    launch_path = str(Path(codex).resolve().parent) + os.pathsep + environment_path
    spec = {
        "Label": paths["label"],
        "ProgramArguments": [executable, "-m", "colony", "--config", str(pinned_config),
                             "--database", str(db_path), "supervise", "--root", str(root), "--port", str(port)],
        "WorkingDirectory": str(runtime),
        "EnvironmentVariables": {"PATH": launch_path, "PYTHONUNBUFFERED": "1"},
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        # A graceful stop drains already-started bounded calls. Give launchd
        # enough time to let that finish before its forced termination deadline.
        "ExitTimeOut": max(600, max(int(config.get("autonomy", {}).get(key, default))
                                    for key, default in (("author_timeout_seconds", 600),
                                                         ("review_timeout_seconds", 240),
                                                         ("planner_timeout_seconds", 180))) + 120),
        "StandardOutPath": str(logs / "supervisor.stdout.log"),
        "StandardErrorPath": str(logs / "supervisor.stderr.log"),
        "ProcessType": "Background",
    }
    paths["plist"].parent.mkdir(parents=True, exist_ok=True)
    temporary = paths["plist"].with_suffix(".plist.tmp")
    with temporary.open("wb") as stream:
        plistlib.dump(spec, stream, sort_keys=True)
    temporary.chmod(0o600)
    os.replace(temporary, paths["plist"])
    metadata = {"label": paths["label"], "deployment_id": deployment_id,
                "runtime": str(runtime), "config": str(pinned_config), "database": str(db_path),
                "port": port, "installed_at": datetime.now(timezone.utc).isoformat(),
                "plist": str(paths["plist"]), "python": executable, "codex": str(Path(codex).resolve())}
    _write_json(paths["metadata"], metadata)
    _launchctl(["bootout", paths["domain"] + "/" + paths["label"]], required=False)
    _launchctl(["bootstrap", paths["domain"], str(paths["plist"])])
    return {**metadata, "installed": True, "started": True,
            "url": "http://127.0.0.1:%d/" % port}


def start_service(root, *, home=None):
    paths = _paths(root, home)
    metadata = _read_metadata(paths)
    if not metadata or not paths["plist"].is_file():
        raise ValueError("Service is not installed; install it first")
    target = paths["domain"] + "/" + paths["label"]
    loaded = _launchctl(["print", target], required=False).returncode == 0
    if not loaded:
        _launchctl(["bootstrap", paths["domain"], str(paths["plist"])])
    else:
        _launchctl(["kickstart", target])
    return {"installed": True, "started": True, "label": paths["label"]}


def stop_service(root, *, home=None):
    paths = _paths(root, home)
    _launchctl(["bootout", paths["domain"] + "/" + paths["label"]], required=False)
    # Bootout unloads KeepAlive as well as terminating the process. A plain kill
    # would cause launchd to restart it immediately.
    return {"installed": paths["plist"].is_file(), "started": False, "label": paths["label"]}


def service_status(root, *, home=None):
    paths = _paths(root, home)
    metadata = _read_metadata(paths)
    result = _launchctl(["print", paths["domain"] + "/" + paths["label"]], required=False)
    pid = None
    state = "unloaded"
    if result.returncode == 0:
        state = "loaded"
        depth = 0
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped == "}":
                depth = max(0, depth - 1)
                continue
            # launchctl also prints state and pid inside resource coalitions
            # and other nested records. Only the job's own fields describe it.
            if depth == 1:
                key, separator, value = stripped.partition(" = ")
                if separator and key == "pid" and value.isdigit():
                    pid = int(value)
                elif separator and key == "state":
                    state = value
            if stripped.endswith("= {"):
                depth += 1
    return {"installed": bool(metadata and paths["plist"].is_file()), "loaded": result.returncode == 0,
            "running": result.returncode == 0 and pid is not None, "pid": pid, "state": state,
            "label": paths["label"], "deployment_id": (metadata or {}).get("deployment_id"),
            "url": "http://127.0.0.1:%d/" % metadata["port"] if metadata else None}


def uninstall_service(root, *, home=None):
    paths = _paths(root, home)
    stop_service(root, home=home)
    if paths["plist"].exists():
        paths["plist"].unlink()
    if paths["metadata"].exists():
        paths["metadata"].unlink()
    return {"installed": False, "started": False, "label": paths["label"],
            "evidence_retained": True}
