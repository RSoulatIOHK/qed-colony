"""Bounded, observable Codex execution. Publication remains a controller action.

This is a local pilot: a Git worktree and the Codex sandbox are not a substitute
for an independently administered VM or credential broker.
"""

import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import sqlite3
import subprocess
import time
from typing import Optional
import uuid

from .store import Store


MAX_LOG_BYTES = 8 * 1024 * 1024
MAX_SUMMARY_CHARS = 16000
MAX_EVENT_BYTES = 1024 * 1024
PIPE_CHUNK_BYTES = 64 * 1024


def _git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments], check=True,
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()


def _signal_group(process, sig):
    try:
        os.killpg(process.pid, sig)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Darwin can report EPERM for a group containing only an unreaped
        # leader. Reap it and retry; a real permission failure still propagates.
        try:
            process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            raise PermissionError("Cannot signal the worker process group")
        try:
            os.killpg(process.pid, sig)
            return True
        except ProcessLookupError:
            return False


def _stop_process(process, grace_seconds=1):
    """Stop the whole process group, including children of an exited leader."""
    process.poll()
    signalled = _signal_group(process, signal.SIGTERM)
    if signalled:
        deadline = time.monotonic() + grace_seconds
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass
        # The leader may exit immediately while children still need the grace.
        time.sleep(max(0, deadline - time.monotonic()))
    # Waiting for the leader alone cannot detect a child that ignores SIGTERM.
    _signal_group(process, signal.SIGKILL)
    process.wait(timeout=5)


def _reserve_slot(db_path, run_id, max_concurrency, timeout):
    """Coordinate independently launched controllers under one SQLite lock."""
    with sqlite3.connect(str(db_path), timeout=15) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""CREATE TABLE IF NOT EXISTS worker_runs (
            id TEXT PRIMARY KEY, status TEXT NOT NULL, expires REAL NOT NULL
        )""")
        now = time.time()
        conn.execute("UPDATE worker_runs SET status='expired' WHERE status='active' AND expires<?", (now,))
        active = conn.execute("SELECT COUNT(*) FROM worker_runs WHERE status='active'").fetchone()[0]
        if active >= max_concurrency:
            raise RuntimeError("Worker concurrency cap reached (%s)" % max_concurrency)
        # Covers setup, bounded inference, process termination, and recording.
        conn.execute("INSERT INTO worker_runs VALUES(?,?,?)", (run_id, "active", now + timeout + 120))


def _release_slot(db_path, run_id):
    with sqlite3.connect(str(db_path), timeout=15) as conn:
        conn.execute("UPDATE worker_runs SET status='finished' WHERE id=?", (run_id,))


def _refresh_slot(db_path, run_id, timeout):
    # Setup consumed part of the initial reservation. Extend it before inference.
    with sqlite3.connect(str(db_path), timeout=15) as conn:
        conn.execute("UPDATE worker_runs SET expires=? WHERE id=? AND status='active'",
                     (time.time() + timeout + 120, run_id))


def _consume_event(line, usage, final_text):
    try:
        event = json.loads(line.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return usage, final_text, None
    if not isinstance(event, dict):
        return usage, final_text, None
    if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
        usage = event["usage"]
    failure = None
    if event.get("type") in {"turn.failed", "error"}:
        failure = "Worker reported an error; inspect its private local log"
    item = event.get("item")
    if (event.get("type") == "item.completed" and isinstance(item, dict)
            and item.get("type") == "agent_message" and isinstance(item.get("text"), str)):
        final_text = item["text"][:MAX_SUMMARY_CHARS]
    return usage, final_text, failure


def _stream_process(process, prompt, log_path, started, timeout, heartbeat):
    """Multiplex bounded binary reads and prompt writes under one deadline.

    POSIX nonblocking pipes avoid both a blocked prompt writer and unbounded
    reader queues. No background I/O thread can outlive the controller.
    """
    prompt_bytes = memoryview(prompt.encode("utf-8"))
    sent, total_bytes, pending = 0, 0, bytearray()
    usage, final_text, failure = {}, "", None
    heartbeat_at = started
    stdout_open = True
    with selectors.DefaultSelector() as selector, log_path.open("wb") as log:
        for pipe in (process.stdin, process.stdout):
            os.set_blocking(pipe.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        while stdout_open or process.poll() is None:
            now = time.monotonic()
            remaining = timeout - (now - started)
            if remaining <= 0:
                failure = "Worker exceeded its %s second wall-time limit" % timeout
                break
            if now - heartbeat_at >= 20:
                heartbeat()
                heartbeat_at = time.monotonic()
                continue  # Recheck the deadline after a possibly contended write.
            for key, _ in selector.select(timeout=min(0.2, remaining)):
                if key.data == "stdin":
                    try:
                        sent += os.write(key.fd, prompt_bytes[sent:sent + PIPE_CHUNK_BYTES])
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        failure = "Worker closed input before receiving the complete prompt"
                        break
                    if sent == len(prompt_bytes):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                    continue
                try:
                    chunk = os.read(key.fd, PIPE_CHUNK_BYTES)
                except BlockingIOError:
                    continue
                if not chunk:
                    stdout_open = False
                    selector.unregister(process.stdout)
                    if pending:
                        usage, final_text, event_failure = _consume_event(pending, usage, final_text)
                        failure = failure or event_failure
                        pending.clear()
                    continue
                allowed = min(len(chunk), max(0, MAX_LOG_BYTES - total_bytes))
                log.write(chunk[:allowed])
                log.flush()
                total_bytes += len(chunk)
                if total_bytes > MAX_LOG_BYTES:
                    failure = "Worker exceeded its local output limit"
                    break
                pending.extend(chunk)
                while True:
                    newline = pending.find(b"\n")
                    if newline < 0:
                        break
                    if newline > MAX_EVENT_BYTES:
                        failure = "Worker exceeded its per-event output limit"
                        break
                    line = bytes(pending[:newline])
                    del pending[:newline + 1]
                    usage, final_text, event_failure = _consume_event(line, usage, final_text)
                    failure = failure or event_failure
                if len(pending) > MAX_EVENT_BYTES:
                    failure = "Worker exceeded its per-event output limit"
                if failure:
                    break
            if failure:
                break
    # Also clean up children that detached their output before the leader exited.
    _stop_process(process)
    return process.returncode, usage, final_text, failure


def build_prompt(task, revision, sandbox):
    criteria = "\n".join("- " + str(item) for item in task.get("acceptance", []))
    mode = ("This is a read-only research task. Return your complete proposal as your final answer."
            if sandbox == "read-only" else
            "You may edit scoped implementation files in this worktree. Return a review summary and checks.")
    return """You are a bounded worker in QED Colony.
Read AGENTS.md and the relevant project files. The prover architecture is open.
Task: {task_id}: {title}
Role: {role}
Starting revision: {revision}

{description}

Acceptance criteria:
{criteria}

{mode}
Do not push, commit, open PRs, merge, deploy, contact other people, install global
dependencies, change credentials, increase permissions, or spawn other agents.
Do not change policy, benchmark specifications, or the controller to satisfy this
task. Do not claim unmeasured results. A successful process is not a proof.
The controller will collect your artifacts and arrange independent review.
""".format(task_id=task["id"], title=task["title"], role=task["role"],
           revision=revision, description=task.get("description", ""),
           criteria=criteria, mode=mode)


def run_once(root: Path, db_path: Path, role: Optional[str] = None,
             timeout: int = 180, agent_id: Optional[str] = None,
             sandbox: str = "read-only") -> dict:
    """Claim and execute at most one task; a successful result always enters review."""
    root, db_path = Path(root).resolve(), Path(db_path).resolve()
    if sandbox not in {"read-only", "workspace-write"}:
        raise ValueError("Only read-only and workspace-write sandboxes are supported")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be an integer between 1 and 3600 seconds")
    config_path = root / "colony.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    if not isinstance(config, dict) or not isinstance(config.get("workers", {}), dict):
        raise ValueError("Worker configuration must be a JSON object")
    policy = config.get("workers", {})
    limit = policy.get("max_concurrency", 4)
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("workers.max_concurrency must be between 1 and 16")
    max_timeout = policy.get("max_timeout_seconds", 180)
    if type(max_timeout) is not int or not 1 <= max_timeout <= 3600:
        raise ValueError("workers.max_timeout_seconds must be between 1 and 3600")
    if timeout > max_timeout:
        raise ValueError("Requested timeout exceeds workers.max_timeout_seconds (%s)" % max_timeout)
    allowed = policy.get("allowed_sandboxes", ["read-only"])
    if (not isinstance(allowed, list) or not allowed
            or any(not isinstance(value, str) or value not in {"read-only", "workspace-write"} for value in allowed)):
        raise ValueError("workers.allowed_sandboxes must list supported sandbox modes")
    if sandbox not in allowed:
        raise ValueError("Requested sandbox is not permitted by workers.allowed_sandboxes")
    lease_seconds = policy.get("lease_seconds", 300)
    if type(lease_seconds) is not int or not 120 <= lease_seconds <= 86400:
        raise ValueError("workers.lease_seconds must be between 120 and 86400")
    binary = shutil.which("codex")
    if not binary:
        raise RuntimeError("Install and authenticate the Codex CLI before running a worker")
    run_id = uuid.uuid4().hex[:12]
    agent_id = agent_id or "worker-" + run_id
    store = Store(db_path).initialize()
    _reserve_slot(db_path, run_id, limit, timeout)
    task, process = None, None
    worktree, run_directory = None, None
    try:
        store.register_agent(agent_id, "Codex " + (role or "worker"), role or "generalist")
        task = store.claim(agent_id, role=role, lease_seconds=lease_seconds)
        if not task:
            return {"status": "idle", "agent_id": agent_id, "message": "No eligible task"}
        safe_id = re.sub(r"[^a-z0-9-]", "-", task["id"].lower())[:48]
        branch = "codex/" + safe_id + "-" + run_id
        revision = _git(root, "rev-parse", "HEAD")
        run_directory = root / ".colony" / "runs" / run_id
        worktree = root / ".colony" / "worktrees" / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        worktree.parent.mkdir(parents=True, exist_ok=True)
        _git(root, "worktree", "add", "-b", branch, str(worktree), revision)
        store.record_event("worker.started", agent_id, "Started bounded %s worker" % sandbox,
                           task["id"], {"branch": branch, "revision": revision,
                                        "timeout_seconds": timeout, "sandbox": sandbox})
        result_path = run_directory / "result.txt"
        command = [binary, "exec", "--ephemeral", "--json", "--color", "never",
                   "--sandbox", sandbox, "--cd", str(worktree),
                   "--output-last-message", str(result_path), "-"]
        prompt = build_prompt(task, revision, sandbox)
        # Logs remain local and ignored. Public state receives action milestones
        # and the final research artifact, never raw private reasoning items.
        environment = dict(os.environ)
        for secret in ("GH_TOKEN", "GITHUB_TOKEN", "GITHUB_ADMIN_TOKEN"):
            environment.pop(secret, None)
        store.heartbeat(task["id"], agent_id, lease_seconds=lease_seconds)
        _refresh_slot(db_path, run_id, timeout)
        started = time.monotonic()
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, bufsize=0,
                                   start_new_session=True, env=environment)
        exit_code, usage, final_text, failure = _stream_process(
            process, prompt, run_directory / "events.jsonl", started, timeout,
            lambda: store.heartbeat(task["id"], agent_id, lease_seconds=lease_seconds))
        if result_path.exists():
            with result_path.open("r", encoding="utf-8", errors="replace") as result_file:
                final_text = result_file.read(MAX_SUMMARY_CHARS)
        final_text = final_text.strip()[:MAX_SUMMARY_CHARS]
        if exit_code != 0 and not failure:
            failure = "Codex exited with code %s; inspect its private local log" % exit_code
        if not failure and not final_text:
            failure = "Worker returned no reviewable final artifact"
        diff = _git(root, "-C", str(worktree), "status", "--porcelain")
        status = "failed" if failure else "review"
        summary = failure or final_text
        store.transition(task["id"], status, agent_id, summary=summary, branch=branch)
        store.record_event("worker.finished", agent_id,
                           "Bounded run %s; %s" % (status, "changes retained for review" if diff else "research artifact recorded"),
                           task["id"], {"exit_code": exit_code, "elapsed_seconds": round(time.monotonic()-started, 3),
                                        "usage": usage, "cost_usd": None,
                                        "has_changes": bool(diff), "branch": branch})
        return {"status": status, "task_id": task["id"], "agent_id": agent_id,
                "branch": branch, "worktree": str(worktree), "result_path": str(result_path),
                "usage": usage, "summary": summary}
    except BaseException as exc:
        if process is not None:
            _stop_process(process)
        if task is not None:
            try:
                store.transition(task["id"], "failed", agent_id,
                                 summary="Controller stopped this run: " + type(exc).__name__)
            except (PermissionError, ValueError):
                pass  # Another controller recovered the lease; do not overwrite it.
        raise
    finally:
        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
        _release_slot(db_path, run_id)
