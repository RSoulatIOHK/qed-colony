"""Pin and schedule local GitHub Project synchronization independently of agents.

The LaunchAgent runs the reviewed script using the user's existing gh CLI login.
Its deployment contains no copied credentials, model policy, or controller state.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse
import uuid

from .service import _write_json


def _paths(root, home=None):
    root = Path(root).resolve()
    label = "io.qed-colony.project-sync." + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    return {"root": root, "label": label, "domain": "gui/%s" % os.getuid(),
            "plist": Path(home or Path.home()) / "Library" / "LaunchAgents" / (label + ".plist"),
            "metadata": root / ".colony" / "project-sync" / "service.json"}


def _launchctl(arguments, required=True):
    result = subprocess.run(["/bin/launchctl"] + list(arguments), capture_output=True,
                            text=True, timeout=15, check=False)
    if required and result.returncode:
        raise RuntimeError("Project service launchctl %s failed: %s" %
                           (arguments[0], result.stderr.strip()[:1000]))
    return result


def _read_metadata(paths):
    if not paths["metadata"].is_file():
        return None
    data = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("label") != paths["label"]:
        raise ValueError("Project service metadata does not belong to this checkout")
    return data


def _project_url(value):
    if not isinstance(value, str):
        raise ValueError("Configure a GitHub Projects v2 URL before installing the project service")
    parsed = urlparse(value)
    match = re.fullmatch(r"/(users|orgs)/([A-Za-z0-9-]+)/projects/([1-9][0-9]*)(?:/views/[1-9][0-9]*)?/?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or not match or parsed.query or parsed.fragment:
        raise ValueError("Project URL must be an HTTPS github.com users/orgs Projects v2 URL")
    return "https://github.com/%s/%s/projects/%s" % match.group(1, 2, 3)


def _repository(value):
    if not isinstance(value, str):
        raise ValueError("Configure a GitHub repository before installing the project service")
    match = re.fullmatch(r"(?:https://github\.com/)?([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", value)
    if not match or match[2] in {".", ".."}:
        raise ValueError("Repository must be OWNER/REPO or an HTTPS github.com repository URL")
    return "%s/%s" % match.group(1, 2)


def install_service(root, config_path, port=7331, interval=120, *, repository=None,
                    project_url=None, home=None, python_executable=None, path_value=None):
    """Install/start a periodic, non-overlapping LaunchAgent with pinned sources."""
    if sys.platform != "darwin":
        raise ValueError("The Project sync service currently requires macOS launchd")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("Project service port must be between 1 and 65535")
    if isinstance(interval, bool) or not isinstance(interval, int) or not 30 <= interval <= 86400:
        raise ValueError("Project service interval must be between 30 and 86400 seconds")
    paths = _paths(root, home)
    root = paths["root"]
    source = root / "scripts" / "sync_github_project.py"
    if not source.is_file() or source.is_symlink():
        raise ValueError("The operational root must contain a regular Project sync script")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Project service configuration must be a JSON object")
    project = config.get("project") or {}
    autonomy = config.get("autonomy") or {}
    if not isinstance(project, dict) or not isinstance(autonomy, dict):
        raise ValueError("Project and autonomy configuration must be JSON objects")
    repository = _repository(repository or autonomy.get("repository") or project.get("repo_url"))
    project_url = _project_url(project_url or project.get("github_project_url") or project.get("project_url"))
    environment_path = os.environ.get("PATH", "") if path_value is None else path_value
    gh = shutil.which("gh", path=environment_path)
    if not gh:
        raise ValueError("GitHub CLI executable was not found in the Project service PATH")
    executable = str(Path(python_executable or sys.executable).resolve())
    if not Path(executable).is_file():
        raise ValueError("Python executable does not exist")
    deployment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    runtime = root / ".colony" / "project-sync" / deployment_id
    runtime.mkdir(parents=True, mode=0o700)
    pinned_script = runtime / "sync_github_project.py"
    shutil.copyfile(source, pinned_script)
    pinned_script.chmod(0o600)
    pinned_config = runtime / "colony.json"
    _write_json(pinned_config, {"project": {"repo_url": "https://github.com/" + repository,
                                          "github_project_url": project_url}})
    logs = root / ".colony" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    state_url = "http://127.0.0.1:%d/api/state" % port
    spec = {
        "Label": paths["label"],
        "ProgramArguments": [executable, "-I", str(pinned_script), "--config", str(pinned_config),
                             "--repository", repository, "--project-url", project_url,
                             "--state-url", state_url, "--apply"],
        "WorkingDirectory": str(runtime),
        "EnvironmentVariables": {"PATH": str(Path(gh).resolve().parent) + os.pathsep + environment_path,
                                 "PYTHONUNBUFFERED": "1"},
        "RunAtLoad": True,
        "StartInterval": interval,
        "ProcessType": "Background",
        "ExitTimeOut": 20,
        "StandardOutPath": str(logs / "project-sync.stdout.log"),
        "StandardErrorPath": str(logs / "project-sync.stderr.log"),
    }
    # launchd does not run two instances of the same job. A missed interval
    # while this process is running is skipped; KeepAlive would create retries.
    paths["plist"].parent.mkdir(parents=True, exist_ok=True)
    temporary = paths["plist"].with_suffix(".plist.tmp")
    with temporary.open("wb") as stream:
        plistlib.dump(spec, stream, sort_keys=True)
    temporary.chmod(0o600)
    os.replace(temporary, paths["plist"])
    metadata = {"label": paths["label"], "deployment_id": deployment_id, "runtime": str(runtime),
                "config": str(pinned_config), "repository": repository, "project_url": project_url,
                "port": port, "interval": interval, "state_url": state_url,
                "installed_at": datetime.now(timezone.utc).isoformat(), "plist": str(paths["plist"]),
                "python": executable, "gh": str(Path(gh).resolve())}
    _write_json(paths["metadata"], metadata)
    _launchctl(["bootout", paths["domain"] + "/" + paths["label"]], required=False)
    _launchctl(["bootstrap", paths["domain"], str(paths["plist"])])
    return {**metadata, "installed": True, "started": True}


def start_service(root, *, home=None):
    paths = _paths(root, home)
    if not _read_metadata(paths) or not paths["plist"].is_file():
        raise ValueError("Project service is not installed; install it first")
    target = paths["domain"] + "/" + paths["label"]
    if _launchctl(["print", target], required=False).returncode:
        _launchctl(["bootstrap", paths["domain"], str(paths["plist"])])
    else:
        _launchctl(["kickstart", target])
    return {"installed": True, "started": True, "label": paths["label"]}


def stop_service(root, *, home=None):
    paths = _paths(root, home)
    _launchctl(["bootout", paths["domain"] + "/" + paths["label"]], required=False)
    return {"installed": paths["plist"].is_file(), "started": False, "label": paths["label"]}


def service_status(root, *, home=None):
    paths = _paths(root, home)
    metadata = _read_metadata(paths)
    result = _launchctl(["print", paths["domain"] + "/" + paths["label"]], required=False)
    pid, exit_code, state, depth = None, None, "unloaded", 0
    if result.returncode == 0:
        state = "loaded"
        for line in result.stdout.splitlines():
            text = line.strip()
            if text == "}":
                depth = max(0, depth - 1)
                continue
            if depth == 1:
                key, separator, value = text.partition(" = ")
                if separator and key == "pid" and value.isdigit():
                    pid = int(value)
                elif separator and key == "state":
                    state = value
                elif separator and key == "last exit code" and re.fullmatch(r"-?\d+", value):
                    exit_code = int(value)
            if text.endswith("= {"):
                depth += 1
    return {"installed": bool(metadata and paths["plist"].is_file()), "loaded": result.returncode == 0,
            "running": result.returncode == 0 and pid is not None, "pid": pid, "state": state,
            "last_exit_code": exit_code, "label": paths["label"],
            "deployment_id": (metadata or {}).get("deployment_id"),
            "project_url": (metadata or {}).get("project_url"), "interval": (metadata or {}).get("interval")}


def uninstall_service(root, *, home=None):
    paths = _paths(root, home)
    stop_service(root, home=home)
    for key in ("plist", "metadata"):
        if paths[key].exists():
            paths[key].unlink()
    return {"installed": False, "started": False, "label": paths["label"], "evidence_retained": True}
