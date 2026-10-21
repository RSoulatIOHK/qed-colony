"""Narrow controller-side Git/GitHub publication.

Models never receive a publication tool. Candidate code is inspected as data here;
only GitHub's protected CI runner executes it. This is a local operational guard,
not credential isolation against a malicious process owned by the same user.
"""

import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import subprocess
import tempfile
import time

from .network import classify_connectivity_error


class PublicationRejected(RuntimeError):
    pass


ENGINEER_FILES = frozenset({"lean/Colony/Tactic.lean", "lean/Colony.lean"})
ENGINEER_PREFIXES = ("lean/Colony/Procedures/", "lean/Colony/Examples/", "research/")
SRE_FILES = frozenset({
    "colony/network_recovery.py", "colony/network.py", "colony/supervisor.py",
    "colony/pipeline.py", "colony/worker.py", "colony/github_broker.py", "colony/operations.py",
    "tests/test_network_recovery.py", "tests/test_network.py", "tests/test_supervisor.py",
    "tests/test_pipeline.py", "tests/test_worker.py", "tests/test_execute_job.py",
    "tests/test_github_broker.py", "tests/test_operations.py", "docs/network-recovery.md", "docs/autonomy.md",
    "docs/pipeline.md", "docs/workers.md",
})
SECRET_PATTERN = re.compile(
    rb"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"\bgh[pousr]_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{30,}|"
    rb"\bsk-[A-Za-z0-9_-]{24,}|\bAKIA[0-9A-Z]{16}\b)"
)
PUBLIC_PATH_PATTERN = re.compile(rb"/(?:Users|home)/[^/\s]+/")


def safe_slug(value):
    return re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-")[:48] or "task"


def validate_public_text(value):
    encoded = value.encode("utf-8")
    if SECRET_PATTERN.search(encoded) or PUBLIC_PATH_PATTERN.search(encoded):
        raise PublicationRejected("Public text contains credential-like or machine-local content")
    return value


def redact_ci_paths(value):
    """Keep actionable filenames while removing CI-specific machine prefixes."""
    # GitHub checks out a repository beneath work/<repo>/<repo>. Resolve this
    # first so the useful repository-relative suffix survives home redaction.
    value = re.sub(r"/(?:home|Users)/runner/work/([^/\s\"':]+)/\1(?=/|[\s\"':]|$)",
                   "<checkout>", value)
    return re.sub(r"/(?:home|Users)/[^/\s\"':]+(?=/|[\s\"':]|$)", "<runner-home>", value)


def checks_state(pr, required_checks):
    """Only exact required check names with a successful conclusion satisfy CI."""
    found = {}
    for check in pr.get("statusCheckRollup") or []:
        name = check.get("name") or check.get("context")
        if not name:
            continue
        state = check.get("conclusion") if check.get("status") == "COMPLETED" else check.get("state")
        if check.get("status") and check.get("status") != "COMPLETED":
            state = "PENDING"
        # Ambiguous duplicate names must not let an earlier success hide failure.
        found.setdefault(name, []).append(str(state or "PENDING").upper())
    states = [state for name in required_checks for state in found.get(name, ["PENDING"])]
    if any(state in {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE", "STALE"} for state in states):
        return "failed"
    return "passed" if states and all(state == "SUCCESS" for state in states) else "pending"


class GitHubBroker:
    def __init__(self, root, policy=None, runner=None):
        self.root = Path(root).resolve()
        self.policy = policy or {}
        self.repository = self.policy.get("repository", "RSoulatIOHK/qed-colony")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repository):
            raise ValueError("Invalid GitHub repository")
        self.base_branch = self.policy.get("base_branch", "main")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", self.base_branch) or ".." in self.base_branch:
            raise ValueError("Invalid base branch")
        self.runner = runner or subprocess.run

    def _run(self, args, cwd=None, binary=False):
        try:
            result = self.runner(args, cwd=str(cwd or self.root), check=True,
                                 capture_output=True, text=not binary, timeout=120)
        except Exception as error:
            classified = classify_connectivity_error(error)
            if classified is not None:
                raise classified from error
            raise
        return result.stdout if binary else result.stdout.strip()

    def git(self, cwd, *args, binary=False):
        return self._run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(cwd), *args], binary=binary)

    def gh(self, *args):
        return self._run(["gh", *args] if args[0] == "api" else ["gh", *args, "--repo", self.repository])

    def probe_connectivity(self):
        """Read-only probe used before resuming any work after a known outage."""
        self.gh("api", "rate_limit")
        return True

    def prepare_worktree(self, cycle):
        branch = "codex/colony-%s-%s" % (safe_slug(cycle["task_id"]), cycle["id"][:12])
        path = self.root / ".colony" / "cycles" / cycle["id"]
        if path.exists():
            actual = self.git(path, "branch", "--show-current")
            if actual != branch:
                raise PublicationRejected("Existing worktree has an unexpected branch")
            return {"worktree": str(path), "branch": branch,
                    "base_sha": cycle.get("base_sha") or self.git(path, "merge-base", "HEAD", "origin/" + self.base_branch)}
        self.git(self.root, "fetch", "origin", self.base_branch)
        base_sha = self.git(self.root, "rev-parse", "origin/" + self.base_branch)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.git(self.root, "worktree", "add", "-b", branch, str(path), base_sha)
        return {"worktree": str(path), "branch": branch, "base_sha": base_sha}

    def validate_changes(self, worktree, role, base_sha):
        worktree = Path(worktree).resolve()
        tracked = self.git(worktree, "diff", "--no-renames", "--name-only", "-z", base_sha, "--", binary=True)
        staged = self.git(worktree, "diff", "--cached", "--no-renames", "--name-only", "-z", base_sha, "--", binary=True)
        committed = self.git(worktree, "diff", "--no-renames", "--name-only", "-z", base_sha, "HEAD", "--", binary=True)
        untracked = self.git(worktree, "ls-files", "--others", "--exclude-standard", "-z", binary=True)
        paths = sorted({item.decode("utf-8", errors="strict") for item in (tracked + staged + committed + untracked).split(b"\0") if item})
        if not paths:
            raise PublicationRejected("Worker produced no publishable changes")
        if len(paths) > int(self.policy.get("max_changed_files", 24)):
            raise PublicationRejected("Candidate exceeds the changed-file cap")
        total = 0
        for name in paths:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or any(part.startswith(".") for part in path.parts):
                raise PublicationRejected("Unsafe candidate path")
            allowed = name.startswith("research/") or (role == "engineer" and
                (name in ENGINEER_FILES or name.startswith(ENGINEER_PREFIXES))) or (role == "sre" and name in SRE_FILES)
            if not allowed:
                raise PublicationRejected("Protected path changed: " + name)
            candidate = worktree / name
            current = candidate
            while current != worktree:
                if current.is_symlink():
                    raise PublicationRejected("Symlinks are not publishable")
                current = current.parent
            if not candidate.exists():
                # Deleting implementation files is reviewable; deleting research evidence is not.
                if name.startswith("research/"):
                    raise PublicationRejected("Research evidence cannot be deleted automatically")
                continue
            if not candidate.is_file():
                raise PublicationRejected("Only regular files are publishable")
            file_limit = int(self.policy.get("max_file_bytes", 256 * 1024))
            if candidate.stat().st_size > file_limit:
                raise PublicationRejected("Candidate exceeds its content cap")
            with candidate.open("rb") as stream:
                content = stream.read(file_limit + 1)
            total += len(content)
            if len(content) > int(self.policy.get("max_file_bytes", 256 * 1024)) or total > int(self.policy.get("max_patch_bytes", 512 * 1024)):
                raise PublicationRejected("Candidate exceeds its content cap")
            if b"\0" in content or SECRET_PATTERN.search(content) or PUBLIC_PATH_PATTERN.search(content):
                raise PublicationRejected("Candidate contains binary, credential-like, or machine-local content")
        # Check the index too: executable files and Git submodules are never needed here.
        index = self.git(worktree, "ls-files", "--stage", "-z", binary=True)
        for entry in index.split(b"\0"):
            if not entry:
                continue
            mode, _, rest = entry.partition(b" ")
            name = rest.partition(b"\t")[2].decode("utf-8", errors="strict")
            if name in paths and mode not in {b"100644"}:
                raise PublicationRejected("Candidate changes an unsupported file mode")
        return paths

    def commit(self, cycle, task):
        worktree = Path(cycle["worktree"])
        if self.git(worktree, "rev-parse", "HEAD") != cycle.get("head_sha", cycle["base_sha"]):
            raise PublicationRejected("Worker changed Git history outside the controller")
        if self.git(worktree, "branch", "--show-current") != cycle["branch"]:
            raise PublicationRejected("Worker changed the controller branch")
        paths = self.validate_changes(worktree, task["role"], cycle["base_sha"])
        self.git(worktree, "add", "--", *paths)
        # Recheck staged modes after adding newly created files.
        self.validate_changes(worktree, task["role"], cycle["base_sha"])
        changed = self.git(worktree, "diff", "--cached", "--name-only", "-z", binary=True)
        if changed:
            self.git(worktree, "commit", "-m", "%s: %s" % (task["id"], task["title"][:160]))
        return self.git(worktree, "rev-parse", "HEAD")

    def find_pr(self, branch):
        values = json.loads(self.gh("pr", "list", "--head", branch, "--state", "all", "--json", "number,url,state,headRefOid,mergedAt"))
        if len(values) > 1:
            raise PublicationRejected("Multiple PRs match a controller branch")
        return values[0] if values else None

    def publish(self, cycle, task, summary):
        self.git(cycle["worktree"], "push", "--set-upstream", "origin", cycle["branch"])
        existing = self.find_pr(cycle["branch"])
        if existing:
            return existing
        governance = task.get("role") == "sre"
        disposition = ("This is a separate governance PR for controller code. A separate read-only model context "
                       "reviews the exact head and required CI must pass. It then awaits controller integration; "
                       "the routine pipeline never automatically merges or deploys this candidate." if governance else
                       "A separate read-only model context reviews the exact head; protected CI must pass before automatic merge.")
        body = ("%s\n\nTask: `%s`\n\n%s\n\nThe colony controller published this candidate. %s "
                "Model output alone is not a proof certificate.\n\n<!-- colony-cycle:%s -->\n") % (
                    task["title"], task["id"], summary[:12000], disposition, cycle["id"])
        validate_public_text(body)
        with tempfile.TemporaryDirectory(prefix="colony-pr-") as directory:
            body_path = Path(directory) / "body.md"
            body_path.write_text(body, encoding="utf-8")
            self.gh("pr", "create", "--base", self.base_branch, "--head", cycle["branch"],
                    "--title", ("Governance: " if governance else "") + "%s: %s" % (task["id"], task["title"][:150]),
                    "--body-file", str(body_path))
        result = self.find_pr(cycle["branch"])
        if result is None:
            raise RuntimeError("PR creation did not return a discoverable pull request")
        return result

    def get_pr(self, number):
        return json.loads(self.gh("pr", "view", str(int(number)), "--json",
            "number,url,state,headRefOid,mergedAt,mergeable,mergeStateStatus,statusCheckRollup"))

    def comment_review(self, number, review, head_sha, cycle_id):
        marker = "<!-- colony-review:%s:%s -->" % (cycle_id, head_sha)
        comments = json.loads(self.gh("api", "repos/%s/issues/%s/comments" % (self.repository, int(number))))
        if any(marker in item.get("body", "") for item in comments):
            return
        text = ("### Colony model review\n\nSeparate read-only model context, published by the controller's "
                "GitHub account. This is a model review, not a GitHub approval by another person.\n\n"
                "Head: `%s`\n\nVerdict: **%s**\n\n%s\n\n") % (head_sha, review["verdict"], review["summary"])
        for finding in review.get("findings", []):
            text += "- %s\n" % finding
        text += "\n" + marker + "\n"
        validate_public_text(text)
        with tempfile.TemporaryDirectory(prefix="colony-review-") as directory:
            path = Path(directory) / "review.md"
            path.write_text(text, encoding="utf-8")
            self.gh("pr", "comment", str(int(number)), "--body-file", str(path))

    def failure_details(self, pr):
        """Read bounded CI data through fixed GitHub commands, never model commands."""
        details = []
        for check in pr.get("statusCheckRollup") or []:
            conclusion = str(check.get("conclusion") or check.get("state") or "").upper()
            if conclusion not in {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}:
                continue
            details.append("%s: %s" % (check.get("name") or check.get("context") or "check", conclusion))
            url = check.get("detailsUrl") or check.get("targetUrl") or ""
            match = re.fullmatch(r"https://github\.com/" + re.escape(self.repository) + r"/actions/runs/([0-9]+)(?:/job/[0-9]+)?", url)
            if match:
                # gh accepts one run ID; no shell or model-provided command is evaluated.
                try:
                    log = self._bounded_log(match.group(1))
                    details.append(log[-12000:])
                except (subprocess.SubprocessError, OSError):
                    details.append("Failed log is unavailable; reproduce the named check locally.")
        return validate_public_text(redact_ci_paths("\n".join(details))[:16000])

    def _bounded_log(self, run_id):
        """Bound both bytes retained and bytes consumed from potentially huge CI logs."""
        command = ["gh", "run", "view", str(int(run_id)), "--log-failed", "--repo", self.repository]
        environment = dict(os.environ, GH_PAGER="cat", GH_PROMPT_DISABLED="1")
        process = subprocess.Popen(command, cwd=str(self.root), stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, env=environment)
        tail, consumed, deadline = bytearray(), 0, time.monotonic() + 30
        try:
            with selectors.DefaultSelector() as selector:
                os.set_blocking(process.stdout.fileno(), False)
                selector.register(process.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline and consumed <= 1024 * 1024:
                    if not selector.select(timeout=0.2):
                        continue
                    chunk = os.read(process.stdout.fileno(), 64 * 1024)
                    if not chunk:
                        break
                    consumed += len(chunk)
                    tail.extend(chunk)
                    if len(tail) > 24000:
                        del tail[:-24000]
            return bytes(tail).decode("utf-8", errors="replace")[-12000:]
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            process.stdout.close()

    def merge(self, number, reviewed_sha):
        current = self.get_pr(number)
        if current.get("mergedAt") or current.get("state") == "MERGED":
            if current.get("headRefOid") != reviewed_sha:
                raise PublicationRejected("Merged PR head differs from the reviewed commit")
            return current
        if current.get("state") != "OPEN" or current.get("headRefOid") != reviewed_sha:
            raise PublicationRejected("PR head changed or PR is not open")
        if current.get("mergeable") != "MERGEABLE" or current.get("mergeStateStatus") not in {"CLEAN", "HAS_HOOKS"}:
            raise PublicationRejected("PR is not cleanly mergeable")
        if checks_state(current, self.policy.get("required_checks", ["control-plane", "lean-seed"])) != "passed":
            raise PublicationRejected("Required CI is not successful for the reviewed head")
        self.gh("pr", "merge", str(int(number)), "--squash", "--match-head-commit", reviewed_sha)
        return self.get_pr(number)
