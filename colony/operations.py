"""Bounded, read-only workflow audits and reviewed follow-up scheduling.

Role proposals are report content. They never grant permissions or update policy.
The pipeline may enqueue accepted follow-ups only after the audit PR is merged.
"""

import json
import re

from .autonomy_store import TERMINAL_PHASES
from .github_broker import PublicationRejected, validate_public_text


TASK_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "role", "description", "acceptance"],
    "properties": {
        "title": {"type": "string", "minLength": 5, "maxLength": 180},
        "role": {"type": "string", "enum": ["engineer", "researcher", "sre"]},
        "description": {"type": "string", "minLength": 20, "maxLength": 6000},
        "acceptance": {"type": "array", "minItems": 1, "maxItems": 6,
                       "items": {"type": "string", "minLength": 5, "maxLength": 1000}},
    },
}
OPS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["report", "role_proposals", "follow_up_tasks"],
    "properties": {
        "report": {"type": "string", "minLength": 1, "maxLength": 12000},
        "role_proposals": {"type": "array", "maxItems": 5,
                           "items": {"type": "string", "minLength": 5, "maxLength": 1000}},
        "follow_up_tasks": {"type": "array", "maxItems": 3, "items": TASK_SCHEMA},
    },
}


def _text(value, minimum, maximum):
    return isinstance(value, str) and minimum <= len(value.strip()) <= maximum and len(value) <= maximum


def parse_operations_output(value):
    """Validate structured model output without accepting model-defined roles."""
    if isinstance(value, str):
        if len(value) > 48000:
            raise PublicationRejected("Operations output exceeds its size limit")
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise PublicationRejected("Operations output must be JSON") from exc
    if not isinstance(value, dict) or set(value) != {"report", "role_proposals", "follow_up_tasks"}:
        raise PublicationRejected("Operations output has an invalid shape")
    roles, followups = value["role_proposals"], value["follow_up_tasks"]
    if (not _text(value["report"], 1, 12000) or not isinstance(roles, list) or len(roles) > 5
            or any(not _text(item, 5, 1000) for item in roles)
            or not isinstance(followups, list) or len(followups) > 3):
        raise PublicationRejected("Operations report exceeds its content bounds")
    for task in followups:
        if (not isinstance(task, dict) or set(task) != {"title", "role", "description", "acceptance"}
                or not isinstance(task["role"], str) or task["role"] not in {"engineer", "researcher", "sre"}
                or not _text(task["title"], 5, 180) or not _text(task["description"], 20, 6000)
                or not isinstance(task["acceptance"], list) or not 1 <= len(task["acceptance"]) <= 6
                or any(not _text(item, 5, 1000) for item in task["acceptance"])):
            raise PublicationRejected("Operations follow-up task is invalid or grants an unsupported role")
    validate_public_text(json.dumps(value, ensure_ascii=False))
    # Return a detached JSON value: a caller cannot mutate the validated input.
    return json.loads(json.dumps(value))


def render_operations_report(payload):
    payload = parse_operations_output(payload)
    parts = [payload["report"].strip(), "## Proposed role charters",
             "Proposals require separate controller authorization; this audit grants no permissions."]
    parts.extend("- " + item for item in payload["role_proposals"])
    if not payload["role_proposals"]:
        parts.append("No new roles proposed.")
    parts.append("## Proposed follow-up tasks")
    if not payload["follow_up_tasks"]:
        parts.append("No follow-up tasks proposed.")
    for task in payload["follow_up_tasks"]:
        parts.extend(["### %s (%s)" % (task["title"], task["role"]), task["description"],
                      "Acceptance criteria:"])
        parts.extend("- " + item for item in task["acceptance"])
    return "\n\n".join(parts) + "\n"


def _safe(value, limit=140):
    value = str(value or "")
    try:
        return validate_public_text(value)[:limit]
    except PublicationRejected:
        return "<redacted operational text>"


def maybe_enqueue_audit(tasks, autonomy, policy):
    """Enqueue at most one periodic audit while the controller owns its lock."""
    every = policy.get("operations_audit_every_cycles", 3)
    if type(every) is not int or every < 0:
        raise ValueError("operations_audit_every_cycles must be a nonnegative integer")
    if not every:
        return None
    snapshot = tasks.snapshot()
    if any(task["role"] == "operations" and task["status"] in {"ready", "running", "review", "blocked"}
           for task in snapshot["tasks"]):
        return None
    cycles = autonomy.list_cycles()
    completed = [cycle for cycle in cycles if cycle["role"] not in {"planner", "operations", "triage"}
                 and cycle["phase"] in TERMINAL_PHASES]
    batch = len(completed) // every
    if not batch:
        return None
    task_id = "OPS%03d" % batch
    if tasks.get_task(task_id) is not None:
        return None
    budget = autonomy.get_budget(policy)
    evidence = {
        "terminal_work_cycles": len(completed),
        "recent_cycles": [{key: _safe(cycle.get(key), 90) for key in ("task_id", "role", "phase")}
                          for cycle in cycles[-8:]],
        "tasks": [{key: _safe(task.get(key), 120 if key == "title" else 60)
                   for key in ("id", "title", "role", "status")} for task in snapshot["tasks"][:12]],
        "budget": {key: budget[key] for key in ("local_date", "used_seconds", "remaining_seconds", "attempts", "remaining_attempts")},
    }
    description = (
        "Audit the colony's actual workflow, failed experiments, review/CI handoffs, backlog, resource use, "
        "and missing role charters. Use the bounded operational evidence below and public repository artifacts. "
        "Distinguish observed failures from hypotheses. Return the required structured report with at most "
        "five role proposals and three scoped follow-up tasks using only engineer, researcher or sre. "
        "Role charters are proposals only: do not grant authority, change policy, deploy, contact people, "
        "or modify files. Follow-up jobs are scheduled only after independent review and merge of this audit.\n\n"
        "Operational evidence: " + json.dumps(evidence, ensure_ascii=False, separators=(",", ":")))
    task = {"id": task_id, "title": "Audit colony operations and propose bounded improvements",
            "role": "operations", "priority": 125, "status": "ready", "depends_on": [],
            "description": description, "acceptance": [
                "Ground the report in actual task, cycle, PR, review, CI and budget evidence; label unknowns",
                "Propose actionable role charters without granting permissions or authority",
                "Propose at most three independent bounded implementation or research tasks with explicit acceptance criteria",
                "Return the strict operations JSON schema; do not edit files or claim proposed work is complete"]}
    inserted = tasks.seed([task])
    if not inserted:
        return None
    tasks.record_event("operations.scheduled", "operations-steward", "Scheduled a periodic workflow audit", task_id,
                       {"terminal_work_cycles": len(completed), "batch": batch})
    return tasks.get_task(task_id)


def enqueue_followups(tasks, cycle, payload, policy):
    """Called by the pipeline only after exact-head reviewed audit merge."""
    payload = parse_operations_output(payload)
    cycle_id = cycle.get("id")
    if not isinstance(cycle_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", cycle_id):
        raise ValueError("Invalid operations cycle ID")
    cap = policy.get("operations_max_backlog", 12)
    if type(cap) is not int or not 0 <= cap <= 100:
        raise ValueError("operations_max_backlog must be an integer between 0 and 100")
    snapshot = tasks.snapshot()
    existing = {task["id"]: task for task in snapshot["tasks"]}
    available = max(0, cap - sum(task["status"] in {"ready", "running"} for task in snapshot["tasks"]))
    scheduled = []
    for index, proposed in enumerate(payload["follow_up_tasks"], 1):
        task_id = "OPSFOLLOW-%s-%d" % (cycle_id, index)
        if task_id in existing:
            scheduled.append(task_id)
            continue
        if not available:
            continue
        task = dict(proposed, id=task_id, priority=65, status="ready", depends_on=[])
        if tasks.seed([task]):
            available -= 1
            tasks.record_event("operations.followup", "operations-steward", "Queued an accepted operations follow-up",
                               task_id, {"operations_cycle": cycle_id})
        scheduled.append(task_id)
    return scheduled
