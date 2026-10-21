#!/usr/bin/env python3
"""Mirror repository work to a configured public GitHub Projects v2 board.

Reads and plans by default. --apply permits only adding issue/PR items and
updating their Status field. Authentication remains owned by the gh CLI.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler


LANES = ("Todo", "Ready", "In progress", "In review", "Blocked", "Done")
ISSUE_FIELDS = """id number title body url state labels(first:100){nodes{name}}"""
PR_FIELDS = """id number title body url state merged isDraft headRefOid reviewDecision
 mergeable labels(first:100){nodes{name}}
 closingIssuesReferences(first:100){nodes{id}}
 comments(last:30){nodes{body author{login}}}
 commits(last:1){nodes{commit{statusCheckRollup{state}}}}"""
PROJECT_QUERY = """query($owner:String!, $number:Int!){
 OWNER(login:$owner){projectV2(number:$number){id url public closed viewerCanUpdate
 field(name:"Status"){... on ProjectV2SingleSelectField{id options{id name}}}}}}
"""
ITEMS_QUERY = """query($project:ID!, $cursor:String){node(id:$project){
 ... on ProjectV2{items(first:100,after:$cursor){nodes{id content{
 ... on Issue{id} ... on PullRequest{id}}
 fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{optionId}}}
 pageInfo{hasNextPage endCursor}}}}}"""
ADD_ITEM = """mutation($project:ID!, $content:ID!){addProjectV2ItemById(
 input:{projectId:$project,contentId:$content}){item{id}}}"""
SET_STATUS = """mutation($project:ID!, $item:ID!, $field:ID!, $option:String!){
 updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,
 value:{singleSelectOptionId:$option}}){projectV2Item{id}}}"""


class SyncError(Exception):
    """A safe-to-display failure without raw API responses or credentials."""


class GitHub:
    def __init__(self):
        self.deadline = time.monotonic() + 300

    def graphql(self, query, **variables):
        # JSON on stdin avoids shell interpolation and command-line token copies.
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise SyncError("The five-minute sync deadline elapsed; completed writes, if any, remain safe to reconcile.")
        try:
            result = subprocess.run(
                ["gh", "api", "graphql", "--input", "-"],
                input=json.dumps({"query": query, "variables": variables}),
                text=True, capture_output=True, timeout=min(60, remaining), check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SyncError("GitHub CLI unavailable or request timed out; no retry was attempted.") from exc
        if result.returncode:
            raise SyncError("GitHub request failed. Check gh authentication, Projects access, and connectivity; raw output withheld.")
        try:
            response = json.loads(result.stdout)
        except ValueError as exc:
            raise SyncError("GitHub returned an invalid response.") from exc
        if response.get("errors") or not isinstance(response.get("data"), dict):
            raise SyncError("GitHub rejected the query. Check Projects permissions; raw output withheld.")
        return response["data"]


def project_reference(url=None, owner=None, number=None, owner_type="user"):
    if url:
        parsed = urlparse(url)
        match = re.fullmatch(r"/(users|orgs)/([A-Za-z0-9-]+)/projects/([1-9][0-9]*)(?:/views/[1-9][0-9]*)?/?", parsed.path)
        if parsed.scheme != "https" or parsed.netloc != "github.com" or not match or parsed.query or parsed.fragment:
            raise SyncError("Project URL must be an HTTPS github.com users/orgs Projects v2 URL.")
        return match[2], int(match[3]), "organization" if match[1] == "orgs" else "user"
    if not owner or not re.fullmatch(r"[A-Za-z0-9-]+", owner) or not number or number < 1:
        raise SyncError("Configure project.github_project_url or supply --project-url (or --owner and --number).")
    return owner, number, owner_type


def repository_reference(value):
    match = re.fullmatch(r"(?:https://github\.com/)?([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", value or "")
    if not match:
        raise SyncError("Repository must be OWNER/REPO or an HTTPS github.com repository URL.")
    return match[1], match[2]


def load_project(api, owner, number, owner_type):
    project = (api.graphql(PROJECT_QUERY.replace("OWNER", owner_type), owner=owner, number=number)
               .get(owner_type) or {}).get("projectV2")
    if not project or not project.get("public") or project.get("closed"):
        raise SyncError("The configured project must exist, be public, and be open. No project settings were changed.")
    field = project.get("field") or {}
    options = {option["name"]: option["id"] for option in field.get("options", [])}
    if not field.get("id") or any(lane not in options for lane in LANES):
        raise SyncError("Create a Status single-select field with: " + ", ".join(LANES) + ". No schema was changed.")
    project["status_field"] = field["id"]
    project["options"] = options
    return project


def repository_items(api, owner, name, kind):
    fields = PR_FIELDS if kind == "pullRequests" else ISSUE_FIELDS
    query = """query($owner:String!, $name:String!, $cursor:String){
 repository(owner:$owner,name:$name){isPrivate COLLECTION(first:100,after:$cursor){
 nodes{FIELDS} pageInfo{hasNextPage endCursor}}}}"""
    query = query.replace("COLLECTION", kind).replace("FIELDS", fields)
    cursor, result = None, []
    while True:
        repository = api.graphql(query, owner=owner, name=name, cursor=cursor).get("repository")
        if repository is None:
            raise SyncError("Repository unavailable; no board changes were made.")
        if repository.get("isPrivate"):
            raise SyncError("Only a public repository may be mirrored to this public board.")
        page = repository[kind]
        result.extend(dict(item, kind="pr" if kind == "pullRequests" else "issue") for item in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return result
        cursor = page["pageInfo"]["endCursor"]


def project_items(api, project_id):
    cursor, result = None, {}
    while True:
        node = api.graphql(ITEMS_QUERY, project=project_id, cursor=cursor).get("node")
        if not node:
            raise SyncError("Project items unavailable; no board changes were made.")
        page = node["items"]
        for item in page["nodes"]:
            if item.get("content"):
                result[item["content"]["id"]] = item
        if not page["pageInfo"]["hasNextPage"]:
            return result
        cursor = page["pageInfo"]["endCursor"]


def labels(item):
    return {label["name"].lower() for label in (item.get("labels") or {}).get("nodes", [])}


def model_review(item, author):
    """Read only controller-authored review markers for the current commit."""
    sha = item.get("headRefOid")
    if not sha or not author:
        return None
    marker = re.compile(r"<!-- colony-review:[A-Za-z0-9_-]+:" + re.escape(sha) + r" -->")
    for comment in reversed((item.get("comments") or {}).get("nodes", [])):
        body = comment.get("body", "")
        if (comment.get("author") or {}).get("login", "").lower() == author.lower() and marker.search(body):
            verdict = re.search(r"Verdict: \*\*(approve|changes_requested|reject)\*\*", body)
            if verdict:
                return verdict[1]
    return None


def pr_lane(item, review_author=None):
    if item.get("merged") or item.get("state") == "MERGED":
        return "Done", "pull request merged"
    if item.get("state") == "CLOSED":
        return "Blocked", "pull request closed without merging"
    if "blocked" in labels(item) or "status:blocked" in labels(item):
        return "Blocked", "explicit blocked label"
    verdict = model_review(item, review_author)
    if verdict == "reject":
        return "Blocked", "current candidate rejected by the controller model review"
    if item.get("reviewDecision") == "CHANGES_REQUESTED" or verdict == "changes_requested":
        return "Blocked", "changes requested on the current candidate"
    if item.get("mergeable") == "CONFLICTING":
        return "Blocked", "merge conflicts"
    for commit in (item.get("commits") or {}).get("nodes", []):
        if ((commit.get("commit") or {}).get("statusCheckRollup") or {}).get("state") in {"FAILURE", "ERROR"}:
            return "Blocked", "current head checks failed"
    if item.get("isDraft"):
        return "In progress", "draft pull request"
    return "In review", "open pull request; review/CI/merge gates remain"


def issue_lane(item, linked_prs, review_author=None):
    if item.get("state") == "CLOSED":
        return "Done", "issue closed"
    names = labels(item)
    for lane, aliases in (("Blocked", {"blocked", "status:blocked"}),
                          ("In progress", {"in progress", "status:in-progress"}),
                          ("In review", {"in review", "status:in-review"}),
                          ("Ready", {"ready", "status:ready"})):
        if names & aliases:
            return lane, "explicit issue status label"
    active = [pr for pr in linked_prs if pr.get("state") == "OPEN"]
    if active:
        lanes = [pr_lane(pr, review_author) for pr in active]
        for wanted in ("Blocked", "In progress", "In review"):
            if any(lane == wanted for lane, _ in lanes):
                return wanted, "linked open pull request"
    # Merging a PR does not prove that an issue's acceptance criteria are complete.
    return "Todo", "open issue without an explicit status or active linked pull request"


def validate_state(state, max_age=300):
    try:
        if not isinstance(state, dict) or not isinstance(state.get("tasks", []), list):
            raise TypeError("Invalid state shape")
        if not isinstance(state.get("autonomy", {}), dict):
            raise TypeError("Invalid autonomy shape")
        generated = datetime.fromisoformat(state["generated_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - generated).total_seconds()
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SyncError("State must be a valid timestamped Colony export.") from exc
    if age < -60 or age > max_age:
        raise SyncError("State export is stale or future-dated; export a fresh state before syncing.")
    return state


def fresh_state(path, max_age=300):
    try:
        with Path(path).open("rb") as stream:
            payload = stream.read(4 * 1024 * 1024 + 1)
        if len(payload) > 4 * 1024 * 1024:
            raise SyncError("Colony state exceeds the 4 MiB sync limit.")
        return validate_state(json.loads(payload), max_age)
    except (OSError, ValueError) as exc:
        raise SyncError("State file could not be read as JSON.") from exc


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SyncError("Local state redirects are not allowed.")


def local_state(url, max_age=300):
    parsed = urlparse(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.path != "/api/state"
            or parsed.query or parsed.fragment):
        raise SyncError("--state-url must be a loopback HTTP /api/state URL without credentials or query parameters.")
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(url, timeout=10) as response:
            payload = response.read(4 * 1024 * 1024 + 1)
        if len(payload) > 4 * 1024 * 1024:
            raise SyncError("Colony state exceeds the 4 MiB sync limit.")
        return validate_state(json.loads(payload), max_age)
    except (OSError, ValueError) as exc:
        raise SyncError("Local Observatory state unavailable; no board writes were attempted.") from exc


def task_for_item(item, tasks):
    for task in tasks:
        if task.get("pr_url") == item["url"]:
            return task
        task_id = str(task.get("id", ""))
        if task_id and (item.get("title", "").startswith(task_id + ":")
                        or "<!-- colony-task:%s -->" % task_id in item.get("body", "")):
            return task
    return None


def recorded_lane(item, state):
    """Return a fresh local workflow override, never an unverified Done claim."""
    task = task_for_item(item, state.get("tasks", []))
    if not task:
        return None
    autonomy = state.get("autonomy") or {}
    cycle = next((cycle for cycle in autonomy.get("cycles", []) if cycle.get("task_id") == task["id"]), {})
    phase = cycle.get("phase")
    if phase in {"failed", "blocked", "needs_review"}:
        if cycle.get("governance_status") == "awaiting_controller_integration":
            return "Blocked", "recorded controller integration required"
        return "Blocked", "recorded cycle requires intervention"
    service = autonomy.get("service") or {}
    if service.get("status") == "budget_limited" and phase in {"queued", "authoring", "reviewing"}:
        return "Blocked", "recorded daily worker budget exhausted"
    if phase in {"authoring", "publishing"}:
        return "In progress", "recorded authoring/publication phase"
    if phase in {"reviewing", "review_publication", "ci", "merging"}:
        return "In review", "recorded review/CI/merge phase"
    status = task.get("status")
    lane = {"ready": "Ready", "running": "In progress", "review": "In review",
            "blocked": "Blocked", "failed": "Blocked", "done": "In review"}.get(status, "Todo")
    return lane, "recorded task status: " + str(status)


def desired_items(issues, prs, state=None, review_author=None):
    result = []
    for item in issues + prs:
        linked = [pr for pr in prs if item["id"] in {
            issue["id"] for issue in (pr.get("closingIssuesReferences") or {}).get("nodes", [])}]
        lane, reason = pr_lane(item, review_author) if item["kind"] == "pr" else issue_lane(item, linked, review_author)
        # Terminal GitHub records always outrank local state. Hard GitHub blockers
        # also outrank an optimistic local phase (e.g. an author still revising).
        terminal = item.get("state") in {"CLOSED", "MERGED"} or item.get("merged")
        if state and not terminal and lane != "Blocked":
            override = recorded_lane(item, state)
            if override:
                lane, reason = override
            elif linked and item["kind"] == "issue":
                overrides = [recorded_lane(pr, state) for pr in linked if pr.get("state") == "OPEN"]
                overrides = [entry for entry in overrides if entry]
                for wanted in ("Blocked", "In progress", "In review", "Ready"):
                    if any(entry[0] == wanted for entry in overrides):
                        lane, reason = wanted, "recorded linked pull request workflow"
                        break
        result.append({"content_id": item["id"], "url": item["url"], "lane": lane, "reason": reason})
    return result


def sync(api, project, desired, existing, apply=False):
    if apply and not project.get("viewerCanUpdate"):
        raise SyncError("Current gh identity cannot update this project. No board changes were made.")
    actions = []
    for entry in desired:
        current = existing.get(entry["content_id"])
        option = project["options"][entry["lane"]]
        status = (current or {}).get("fieldValueByName") or {}
        if current and status.get("optionId") == option:
            continue
        action = dict(entry, action="update" if current else "add")
        actions.append(action)
        if not apply:
            continue
        item_id = current["id"] if current else api.graphql(
            ADD_ITEM, project=project["id"], content=entry["content_id"])["addProjectV2ItemById"]["item"]["id"]
        api.graphql(SET_STATUS, project=project["id"], item=item_id,
                    field=project["status_field"], option=option)
        existing[entry["content_id"]] = {"id": item_id, "fieldValueByName": {"optionId": option}}
    return actions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="colony.json")
    parser.add_argument("--repository")
    parser.add_argument("--project-url")
    parser.add_argument("--owner")
    parser.add_argument("--number", type=int)
    parser.add_argument("--owner-type", choices=["user", "organization"], default="user")
    parser.add_argument("--review-author", help="Controller GitHub login; defaults to repository owner")
    state_source = parser.add_mutually_exclusive_group()
    state_source.add_argument("--state-file", help="Fresh Colony state export; only selected workflow fields are used")
    state_source.add_argument("--state-url", help="Live loopback HTTP /api/state endpoint; no redirects")
    parser.add_argument("--state-max-age", type=int, default=300)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Add/update project items using gh's current authentication")
    mode.add_argument("--dry-run", action="store_true", help="Explicitly select the default read-only plan")
    args = parser.parse_args(argv)
    try:
        config_path = Path(args.config)
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        repository = args.repository or config.get("autonomy", {}).get("repository") or config.get("project", {}).get("repo_url")
        repo_owner, name = repository_reference(repository)
        project_url = args.project_url or (None if args.owner else config.get("project", {}).get("github_project_url"))
        owner, number, owner_type = project_reference(project_url, args.owner, args.number, args.owner_type)
        if args.state_max_age < 1:
            raise SyncError("--state-max-age must be positive.")
        state = (fresh_state(args.state_file, args.state_max_age) if args.state_file else
                 local_state(args.state_url, args.state_max_age) if args.state_url else None)
        api = GitHub()
        project = load_project(api, owner, number, owner_type)
        issues = repository_items(api, repo_owner, name, "issues")
        prs = repository_items(api, repo_owner, name, "pullRequests")
        existing = project_items(api, project["id"])
        desired = desired_items(issues, prs, state, args.review_author or repo_owner)
        actions = sync(api, project, desired, existing, args.apply)
        print(json.dumps({"mode": "applied" if args.apply else "dry_run", "project_url": project["url"],
                          "source": "github_and_fresh_colony_state" if state else "github",
                          "examined": len(desired), "changes": actions}, indent=2))
        return 0
    except (SyncError, ValueError, OSError) as exc:
        print("Project sync stopped: " + (str(exc) if isinstance(exc, SyncError) else "Configuration could not be read as JSON."), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
