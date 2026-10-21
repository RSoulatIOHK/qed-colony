"""Controller-owned, bounded recovery assignments for parked public PRs.

Detection spends no model budget. A root receives at most one read-only triage
and one normal repair cycle; neither a failed recovery nor a governance handoff
creates another generation of model work. Repair publication, review and merge
remain the responsibility of the ordinary pipeline.
"""

import json
import re

from .autonomy_store import TERMINAL_PHASES
from .github_broker import PublicationRejected, validate_public_text
from .store import timestamp


PARKED_PHASES = frozenset({"needs_review", "failed", "blocked"})
REPAIR_ROLES = frozenset({"engineer", "researcher", "sre", "operations"})
TRIAGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["action", "diagnosis", "repair_title", "repair_description", "role"],
    "properties": {
        "action": {"type": "string", "enum": ["repair", "escalate"]},
        "diagnosis": {"type": "string", "minLength": 1, "maxLength": 3000},
        "repair_title": {"type": "string", "maxLength": 180},
        "repair_description": {"type": "string", "maxLength": 6000},
        "role": {"type": "string", "enum": ["", "engineer", "researcher", "sre", "operations"]},
    },
}


def _safe(value, maximum=3000):
    """Operational errors can contain private paths; never copy them publicly."""
    value = str(value or "")
    try:
        return validate_public_text(value)[:maximum]
    except PublicationRejected:
        return "Operational details were redacted; inspect the scoped public artifacts."


def _governance_hold(cycle):
    return (cycle.get("governance_status") == "awaiting_controller_integration"
            and (cycle.get("review") or {}).get("verdict") == "approve"
            and cycle.get("reviewed_sha") == cycle.get("head_sha")
            and bool(cycle.get("head_sha")) and cycle.get("ci_status") == "passed")


def _assign(tasks, autonomy, root, status, owner, reason, next_action, **extra):
    """Persist a changed assignment and emit one event, not one event per poll."""
    data = {"recovery_owner": owner, "recovery_status": status,
            "recovery_reason": _safe(reason), "recovery_next_action": _safe(next_action)}
    data.update(extra)
    changed = any(root.get(key) != value for key, value in data.items())
    if not changed:
        return root
    # A deadline describes this assignment; repeated scans must not move it.
    data["recovery_next_action_deadline"] = timestamp(autonomy.clock() + 24 * 60 * 60)
    updated = autonomy.update_cycle(root["id"], **data)
    tasks.record_event("recovery." + status, "controller", data["recovery_next_action"],
                       root["task_id"], {"root_cycle_id": root["id"], "owner": owner,
                                         "status": status})
    return updated


def _escalate(tasks, autonomy, root, reason, status="escalated"):
    return _assign(tasks, autonomy, root, status, "controller", reason,
                   "Review the recorded blocker and scope a separately authorized next action; "
                   "automatic recovery is exhausted or outside the current worker scope.")


def _source_context(root, task):
    return {"recovery_kind": "triage", "recovery_root_id": root["id"],
            "source_task_id": task["id"], "source_task_title": task["title"],
            "source_task_role": task["role"], "source_task_description": task.get("description", ""),
            "source_task_acceptance": json.loads(json.dumps(task.get("acceptance", []))),
            "source_pr_url": root["pr_url"], "source_head_sha": root.get("head_sha"),
            "source_pr_number": root.get("pr_number"),
            "source_reason": _safe(root.get("last_error") or "Parked public pull request")}


def scan_recoveries(tasks, autonomy, policy):
    """Assign each eligible parked root once while holding the supervisor lock.

    The durable deterministic task IDs also reconcile a crash between creating a
    child cycle and linking it to its parent. No model or GitHub call occurs here.
    """
    cycles = autonomy.list_cycles()
    by_task = {cycle["task_id"]: cycle for cycle in cycles}
    assigned = []
    for root in cycles:
        if (root["phase"] not in PARKED_PHASES or not root.get("pr_url")
                or root.get("recovery_kind") or root["role"] in {"planner", "triage"}
                or root["task_id"].startswith(("TRIAGE-", "REPAIR-"))):
            continue
        if root.get("recovery_status") == "resolved":
            continue
        if _governance_hold(root):
            assigned.append(_assign(tasks, autonomy, root, "awaiting_controller_integration", "controller",
                                    "Exact-head reviewed SRE candidate passed required CI.",
                                    "Review and integrate the approved governance candidate; "
                                    "routine recovery cannot merge or deploy it."))
            continue
        task = tasks.get_task(root["task_id"])
        if task is None or root["role"] not in REPAIR_ROLES or task["role"] != root["role"]:
            assigned.append(_escalate(tasks, autonomy, root,
                                      "Original execution role is unsupported or differs from its task; "
                                      "a read-only substitute cannot satisfy implementation acceptance.",
                                      "controller_scope_review"))
            continue
        repair = by_task.get("REPAIR-" + root["id"])
        triage = by_task.get("TRIAGE-" + root["id"])
        # Store completion and the root's final context write are separate
        # transactions. A crash between them must be able to recheck the remote
        # evidence and finish resolution, without reopening any model stage.
        partial_resolution = (task["status"] == "done" and root.get("recovery_status") == "repair_merged"
                              and repair is not None and repair["phase"] == "done"
                              and repair.get("recovery_kind") == "repair"
                              and repair.get("recovery_root_id") == root["id"]
                              and isinstance(repair.get("pr_url"), str) and bool(repair["pr_url"])
                              and root.get("recovery_repair_cycle_id") == repair["id"]
                              and root.get("recovery_repair_task_id") == repair["task_id"]
                              and triage is not None and root.get("recovery_triage_cycle_id") == triage["id"]
                              and triage.get("recovery_kind") == "triage"
                              and triage.get("recovery_root_id") == root["id"]
                              and task.get("summary") == "Original acceptance satisfied by reviewed replacement " + repair["pr_url"])
        if task["status"] not in {"blocked", "failed", "review"} and not partial_resolution:
            assigned.append(_escalate(tasks, autonomy, root,
                                      "The original task is no longer parked; recovery cannot take ownership "
                                      "of resumed, executing, or independently completed work.",
                                      "controller_scope_review"))
            continue
        if root.get("recovery_status") in {"escalated", "controller_scope_review"}:
            continue
        url = root.get("pr_url")
        match = (re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/([1-9][0-9]*)/?", url)
                 if isinstance(url, str) else None)
        head = root.get("head_sha")
        number = root.get("pr_number")
        if (not match or not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head)
                or (number is not None and (type(number) is not int or number != int(match.group(1))))):
            assigned.append(_escalate(tasks, autonomy, root,
                                      "Recovery requires an unambiguous public source PR and a complete candidate revision.",
                                      "controller_scope_review"))
            continue
        if number is None:
            root = autonomy.update_cycle(root["id"], pr_number=int(match.group(1)))

        if repair is not None:
            # Reconcile an interrupted link write without granting another cycle.
            if repair.get("recovery_root_id") != root["id"] or repair.get("recovery_kind") != "repair":
                repair = autonomy.update_cycle(repair["id"], recovery_kind="repair", recovery_root_id=root["id"])
            link = {"recovery_repair_cycle_id": repair["id"], "recovery_repair_task_id": repair["task_id"]}
            if _governance_hold(repair):
                assigned.append(_assign(tasks, autonomy, root, "awaiting_controller_integration", "controller",
                                        "Repair candidate passed its independent exact-head review and CI.",
                                        "Integrate the approved repair governance PR before resolving the original blocker.",
                                        **link))
            elif repair["phase"] == "done":
                assigned.append(_assign(tasks, autonomy, root, "repair_merged", "controller",
                                        "The linked repair cycle completed its normal publication gates.",
                                        "Reconcile the original acceptance and linked PR using the merged repair evidence.",
                                        **link))
            elif repair["phase"] in PARKED_PHASES:
                assigned.append(_escalate(tasks, autonomy, root,
                                          "The single bounded repair is parked: " + _safe(repair.get("last_error"))))
            elif repair["phase"] == "queued":
                assigned.append(_assign(tasks, autonomy, root, "repair_queued", "repair-author",
                                        "The single linked repair is queued for normal pipeline dispatch.",
                                        "Dispatch the bounded repair when shared model budget permits, then require fresh review and CI.",
                                        **link))
            else:
                assigned.append(_assign(tasks, autonomy, root, "repair_in_progress", "repair-author",
                                        "A single linked repair is passing through the ordinary pipeline.",
                                        "Complete the linked repair with fresh independent review and required CI.", **link))
            continue

        triage_id = "TRIAGE-" + root["id"]
        triage = by_task.get(triage_id)
        if triage is not None:
            if not triage.get("recovery_kind"):
                context = _source_context(root, task)
                try:
                    validate_public_text(json.dumps(context, ensure_ascii=False))
                except PublicationRejected:
                    assigned.append(_escalate(tasks, autonomy, root,
                                              "Original task metadata cannot safely be copied into public recovery work.",
                                              "controller_scope_review"))
                    continue
                triage = autonomy.update_cycle(triage["id"], phase="triaging", **context)
            if triage["phase"] in TERMINAL_PHASES:
                assigned.append(_escalate(tasks, autonomy, root,
                                          "The single read-only triage ended without a runnable repair: "
                                          + _safe(triage.get("last_error") or triage.get("triage_diagnosis"))))
            else:
                assigned.append(_assign(tasks, autonomy, root, "triage_queued", "blocker-triage",
                                        _safe(root.get("last_error") or "Parked public pull request"),
                                        "Run the single bounded read-only triage when shared model budget permits.",
                                        recovery_triage_cycle_id=triage["id"],
                                        source_pr_url=triage["source_pr_url"], source_head_sha=triage["source_head_sha"]))
            continue

        # Reject private source specifications instead of copying them into a
        # public repair task or allowing a scan failure to break the supervisor.
        context = _source_context(root, task)
        try:
            validate_public_text(json.dumps(context, ensure_ascii=False))
        except PublicationRejected:
            assigned.append(_escalate(tasks, autonomy, root,
                                      "Original task metadata cannot safely be copied into public recovery work.",
                                      "controller_scope_review"))
            continue
        triage = autonomy.create_cycle(triage_id, "triage")
        triage = autonomy.update_cycle(triage["id"], phase="triaging", **context)
        assigned.append(_assign(tasks, autonomy, root, "triage_queued", "blocker-triage", context["source_reason"],
                                "Run the single bounded read-only triage when shared model budget permits.",
                                recovery_triage_cycle_id=triage["id"],
                                source_pr_url=context["source_pr_url"], source_head_sha=context["source_head_sha"]))
    return assigned


def _parse(payload):
    if isinstance(payload, str):
        if len(payload) > 12000:
            raise PublicationRejected("Triage output exceeds its size limit")
        try:
            payload = json.loads(payload)
        except ValueError as exc:
            raise PublicationRejected("Triage output must be JSON") from exc
    required = {"action", "diagnosis", "repair_title", "repair_description", "role"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise PublicationRejected("Triage output has an invalid shape")
    if not isinstance(payload["action"], str) or payload["action"] not in {"repair", "escalate"}:
        raise PublicationRejected("Triage action is unsupported")
    for key, maximum in (("diagnosis", 3000), ("repair_title", 180), ("repair_description", 6000), ("role", 20)):
        if not isinstance(payload[key], str) or len(payload[key]) > maximum:
            raise PublicationRejected("Triage field exceeds its content bounds")
    if not payload["diagnosis"].strip() or payload["role"] not in REPAIR_ROLES | {""}:
        raise PublicationRejected("Triage diagnosis or role is invalid")
    if payload["action"] == "repair" and (len(payload["repair_title"].strip()) < 5
                                           or len(payload["repair_description"].strip()) < 20):
        raise PublicationRejected("Triage repair proposal is incomplete")
    validate_public_text(json.dumps(payload, ensure_ascii=False))
    return json.loads(json.dumps(payload))


def apply_triage_result(tasks, autonomy, policy, triage_cycle, payload):
    """Validate a read-only decision and immediately hand off one bounded repair.

    A model can diagnose or propose repair instructions. It cannot change the
    original acceptance, choose a different execution role, or authorize scope.
    The original parked task is never completed by this function.
    """
    root_id = triage_cycle.get("recovery_root_id")
    root = autonomy.get_cycle(root_id) if isinstance(root_id, str) else None
    if (root is None or triage_cycle.get("recovery_kind") != "triage"
            or triage_cycle.get("task_id") != "TRIAGE-" + root["id"]):
        raise PublicationRejected("Triage is not linked to an original root cycle")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", root["id"]):
        raise PublicationRejected("Invalid recovery root ID")
    task = tasks.get_task(root["task_id"])
    if root.get("recovery_status") in {"escalated", "controller_scope_review", "resolved"}:
        current = autonomy.get_cycle(triage_cycle["id"])
        if current["phase"] != "done":
            autonomy.update_cycle(triage_cycle["id"], phase="done", triage_action="cancelled",
                                  triage_diagnosis="The controller already owns or resolved the original blocker.")
        return {"status": root["recovery_status"]}
    if _governance_hold(root) or root["phase"] not in PARKED_PHASES:
        _escalate(tasks, autonomy, root, "Original cycle is no longer a runnable recovery target.")
        autonomy.update_cycle(triage_cycle["id"], phase="done", triage_action="escalate")
        return {"status": "escalated"}
    payload = _parse(payload)
    root = autonomy.update_cycle(root["id"], recovery_diagnosis=payload["diagnosis"])
    if task is not None and task["status"] not in {"blocked", "failed", "review"}:
        _escalate(tasks, autonomy, root,
                  "The original task resumed or completed after triage; no repair was assigned.",
                  "controller_scope_review")
        autonomy.update_cycle(triage_cycle["id"], phase="done", triage_action="escalate",
                              triage_diagnosis=payload["diagnosis"])
        return {"status": "controller_scope_review"}
    original_matches = (task is not None and task["role"] == triage_cycle.get("source_task_role") == root["role"]
                        and task.get("description", "") == triage_cycle.get("source_task_description")
                        and task.get("acceptance", []) == triage_cycle.get("source_task_acceptance")
                        and task["role"] in REPAIR_ROLES)
    if not original_matches or (payload["action"] == "repair" and payload["role"] != task["role"]):
        _escalate(tasks, autonomy, root,
                  "Original task specification changed or triage attempted to change execution scope.",
                  "controller_scope_review")
        autonomy.update_cycle(triage_cycle["id"], phase="done", triage_action="escalate",
                              triage_diagnosis=payload["diagnosis"])
        return {"status": "controller_scope_review"}
    if payload["action"] == "escalate":
        _escalate(tasks, autonomy, root, payload["diagnosis"])
        autonomy.update_cycle(triage_cycle["id"], phase="done", triage_action="escalate",
                              triage_diagnosis=payload["diagnosis"])
        return {"status": "escalated"}

    task_id = "REPAIR-" + root["id"]
    description = (triage_cycle["source_task_description"] + "\n\n"
                   + "Recovery context:\n" + payload["diagnosis"] + "\n\n"
                   + "Bounded repair instructions:\n" + payload["repair_description"] + "\n\n"
                   + "Source PR: " + triage_cycle["source_pr_url"] + "\n"
                   + "Source candidate head: " + str(triage_cycle.get("source_head_sha") or "unknown") + "\n"
                   + "Use a fresh normal candidate from the current main branch. Inspect the linked original "
                   "candidate as source material; never weaken its theorem, assumptions, bounds, acceptance, "
                   "CI or evaluator. Do not claim the original blocker resolved merely by producing a report. "
                   "Stay within the original worker role and existing editable paths.")
    repair_task = {"id": task_id, "title": payload["repair_title"], "description": description,
                   "role": task["role"], "acceptance": triage_cycle["source_task_acceptance"],
                   "priority": 130, "status": "ready", "depends_on": []}
    validate_public_text(json.dumps(repair_task, ensure_ascii=False))
    previous = tasks.get_task(task_id)
    if previous is not None and any(previous.get(key) != repair_task[key]
                                    for key in ("title", "description", "role", "acceptance")):
        _escalate(tasks, autonomy, root, "Existing repair task differs from the single validated recovery proposal.")
        autonomy.update_cycle(triage_cycle["id"], phase="done", triage_action="escalate",
                              triage_diagnosis=payload["diagnosis"])
        return {"status": "escalated"}
    tasks.seed([repair_task])
    repair = autonomy.create_cycle(task_id, task["role"])
    repair = autonomy.update_cycle(repair["id"], recovery_kind="repair", recovery_root_id=root["id"],
                                   source_pr_url=triage_cycle["source_pr_url"],
                                   source_head_sha=triage_cycle.get("source_head_sha"),
                                   source_task_id=task["id"], source_task_title=triage_cycle["source_task_title"],
                                   source_task_role=triage_cycle["source_task_role"],
                                   source_task_description=triage_cycle["source_task_description"],
                                   source_task_acceptance=triage_cycle["source_task_acceptance"])
    autonomy.update_cycle(triage_cycle["id"], phase="done", triage_action="repair",
                          triage_diagnosis=payload["diagnosis"], recovery_repair_cycle_id=repair["id"])
    _assign(tasks, autonomy, root, "repair_queued", "repair-author", payload["diagnosis"],
            "Complete the single bounded repair with fresh independent review and required CI.",
            recovery_triage_cycle_id=triage_cycle["id"], recovery_repair_cycle_id=repair["id"],
            recovery_repair_task_id=task_id)
    return {"status": "repair_queued", "task_id": task_id, "cycle_id": repair["id"]}
