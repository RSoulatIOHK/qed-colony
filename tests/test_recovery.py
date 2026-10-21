import copy
import json
from pathlib import Path
import tempfile
import unittest

from colony.autonomy_store import AutonomyStore
from colony.github_broker import PublicationRejected
from colony.recovery import apply_triage_result, scan_recoveries
from colony.store import Store


PRIVATE_PATH = "/" + "Users/private/"


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.db"
        self.tasks = Store(self.path).initialize()
        self.now = 1800000000
        self.autonomy = AutonomyStore(self.path, clock=lambda: self.now).initialize()
        self.policy = {"max_daily_seconds": 0, "max_daily_attempts": 0}

    def root(self, task_id="T1", role="engineer", **data):
        self.tasks.seed([{"id": task_id, "title": "Complete the original theorem procedure", "role": role,
                          "description": "Prove the original bounded theorem using its original assumptions.",
                          "acceptance": ["Preserve the original theorem statement", "Check the original invalid case"],
                          "status": "blocked"}])
        cycle = self.autonomy.create_cycle(task_id, role)
        context = {"pr_url": "https://github.com/example/project/pull/5", "head_sha": "a" * 40,
                   "last_error": "Revision limit reached after actionable review findings.", "review": None}
        context.update(data)
        return self.autonomy.update_cycle(cycle["id"], phase="needs_review", **context)

    def triage(self, root):
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        return next(cycle for cycle in self.autonomy.list_cycles()
                    if cycle["task_id"] == "TRIAGE-" + root["id"])

    def result(self, role="engineer", action="repair"):
        return {"action": action, "diagnosis": "The branch needs a bounded correction to satisfy the original review.",
                "repair_title": "Correct the original theorem procedure",
                "repair_description": "Inspect the source candidate and implement the missing original proof cases.",
                "role": role}

    def apply(self, triage, payload=None):
        return apply_triage_result(self.tasks, self.autonomy, self.policy, triage,
                                   self.result() if payload is None else payload)

    def test_scan_assigns_public_blocker_without_spending_zero_budget(self):
        root = self.root()
        triage = self.triage(root)
        assignment = self.autonomy.get_cycle(root["id"])
        self.assertEqual(assignment["recovery_owner"], "blocker-triage")
        self.assertEqual(assignment["recovery_status"], "triage_queued")
        self.assertEqual(assignment["recovery_triage_cycle_id"], triage["id"])
        self.assertEqual(assignment["source_pr_url"], root["pr_url"])
        self.assertEqual(assignment["source_head_sha"], root["head_sha"])
        self.assertEqual(assignment["pr_number"], 5)
        self.assertTrue(assignment["recovery_next_action_deadline"].endswith("Z"))
        self.assertEqual(triage["phase"], "triaging")
        self.assertEqual(triage["role"], "triage")
        self.assertIsNone(self.tasks.get_task(triage["task_id"]))
        self.assertEqual(self.autonomy.list_attempts(), [])

    def test_restart_scan_is_idempotent_and_deadline_does_not_drift(self):
        root = self.root()
        triage = self.triage(root)
        first = self.autonomy.get_cycle(root["id"])
        events = len(self.tasks.snapshot()["events"])
        self.now += 300
        self.autonomy = AutonomyStore(self.path, clock=lambda: self.now).initialize()
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        second = self.autonomy.get_cycle(root["id"])
        self.assertEqual(first["recovery_next_action_deadline"], second["recovery_next_action_deadline"])
        self.assertEqual(events, len(self.tasks.snapshot()["events"]))
        self.assertEqual(len(self.autonomy.list_cycles()), 2)
        self.assertEqual(second["recovery_triage_cycle_id"], triage["id"])

    def test_restart_reconciles_cycle_created_before_triage_context_write(self):
        root = self.root()
        interrupted = self.autonomy.create_cycle("TRIAGE-" + root["id"], "triage")
        triage = self.triage(root)
        self.assertEqual(triage["id"], interrupted["id"])
        self.assertEqual(triage["phase"], "triaging")
        self.assertEqual(triage["recovery_root_id"], root["id"])
        self.assertEqual(len(self.autonomy.list_cycles()), 2)

    def test_scans_failed_blocked_and_needs_review_but_not_active_done_or_private(self):
        for phase in ("failed", "blocked", "needs_review", "done", "ci"):
            cycle = self.root(phase)
            self.autonomy.update_cycle(cycle["id"], phase=phase)
        private = self.root("private")
        self.autonomy.update_cycle(private["id"], pr_url=None)
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        triages = [cycle for cycle in self.autonomy.list_cycles() if cycle["role"] == "triage"]
        self.assertEqual(len(triages), 3)

    def test_approved_sre_hold_gets_controller_owner_without_retry(self):
        root = self.root(role="sre", governance_status="awaiting_controller_integration",
                         review={"verdict": "approve"}, reviewed_sha="a" * 40, ci_status="passed")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        root = self.autonomy.get_cycle(root["id"])
        self.assertEqual(root["recovery_status"], "awaiting_controller_integration")
        self.assertEqual(root["recovery_owner"], "controller")
        self.assertEqual(len(self.autonomy.list_cycles()), 1)

    def test_falsely_labelled_governance_hold_without_exact_approval_still_gets_triage(self):
        root = self.root(role="sre", governance_status="awaiting_controller_integration",
                         review={"verdict": "approve"}, reviewed_sha="b" * 40, ci_status="passed")
        self.assertEqual(self.triage(root)["recovery_root_id"], root["id"])

    def test_unknown_infrastructure_profile_escalates_without_fake_research(self):
        root = self.root("I001", role="infrastructure")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        root = self.autonomy.get_cycle(root["id"])
        self.assertEqual(root["recovery_status"], "controller_scope_review")
        self.assertEqual(root["recovery_owner"], "controller")
        self.assertEqual(len(self.autonomy.list_cycles()), 1)

    def test_resumed_running_or_independently_done_source_gets_owner_without_model_triage(self):
        for status in ("ready", "running", "done"):
            root = self.root("source-" + status)
            with self.tasks._connection(write=True) as conn:
                conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, root["task_id"]))
            scan_recoveries(self.tasks, self.autonomy, self.policy)
            current = self.autonomy.get_cycle(root["id"])
            self.assertEqual(current["recovery_status"], "controller_scope_review")
            self.assertEqual(current["recovery_owner"], "controller")
        self.assertFalse(any(cycle["role"] == "triage" for cycle in self.autonomy.list_cycles()))

    def test_missing_head_invalid_url_or_ambiguous_number_escalates_without_model_triage(self):
        invalid = [{"head_sha": None}, {"head_sha": "short"}, {"pr_url": "https://example.com/project/pull/5"},
                   {"pr_number": 6}, {"pr_number": True}]
        for index, context in enumerate(invalid):
            root = self.root("invalid-" + str(index), **context)
            scan_recoveries(self.tasks, self.autonomy, self.policy)
            root = self.autonomy.get_cycle(root["id"])
            self.assertEqual(root["recovery_status"], "controller_scope_review")
            self.assertEqual(root["recovery_owner"], "controller")
        self.assertFalse(any(cycle["role"] == "triage" for cycle in self.autonomy.list_cycles()))

    def test_private_error_is_sanitized_without_breaking_scan(self):
        root = self.root(last_error="Failure in " + PRIVATE_PATH + "checkout with ghp_" + "a" * 30)
        triage = self.triage(root)
        self.assertNotIn("/Users/", json.dumps(triage))
        self.assertNotIn("ghp_", json.dumps(self.autonomy.get_cycle(root["id"])["recovery_reason"]))

    def test_private_original_spec_escalates_without_copying_it(self):
        root = self.root()
        with self.tasks._connection(write=True) as conn:
            conn.execute("UPDATE tasks SET description=? WHERE id=?", ("Read " + PRIVATE_PATH + "task.txt", root["task_id"]))
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "controller_scope_review")
        self.assertEqual(len(self.autonomy.list_cycles()), 1)

    def test_repair_is_queued_immediately_without_triage_report_review(self):
        root = self.root()
        triage = self.triage(root)
        result = self.apply(triage)
        task = self.tasks.get_task(result["task_id"])
        cycle = self.autonomy.get_cycle(result["cycle_id"])
        self.assertEqual(task["status"], "ready")
        self.assertEqual(task["priority"], 130)
        self.assertEqual(cycle["phase"], "queued")
        self.assertEqual(cycle["recovery_kind"], "repair")
        self.assertEqual(cycle["recovery_root_id"], root["id"])
        self.assertEqual(self.autonomy.get_cycle(triage["id"])["phase"], "done")
        self.assertEqual(self.autonomy.list_attempts(), [])
        self.assertEqual(self.tasks.get_task(root["task_id"])["status"], "blocked")
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_diagnosis"], self.result()["diagnosis"])

    def test_queued_repair_remains_truthfully_queued_before_author_dispatch(self):
        root = self.root()
        repair = self.apply(self.triage(root))
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "repair_queued")
        self.assertEqual(self.autonomy.get_cycle(repair["cycle_id"])["phase"], "queued")
        self.autonomy.update_cycle(repair["cycle_id"], phase="authoring")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "repair_in_progress")

    def test_original_description_and_acceptance_are_copied_verbatim(self):
        root = self.root()
        original = self.tasks.get_task(root["task_id"])
        triage = self.triage(root)
        result = self.apply(triage)
        repair = self.tasks.get_task(result["task_id"])
        self.assertEqual(repair["role"], original["role"])
        self.assertEqual(repair["acceptance"], original["acceptance"])
        self.assertTrue(repair["description"].startswith(original["description"]))
        self.assertIn(root["pr_url"], repair["description"])
        self.assertIn(root["head_sha"], repair["description"])
        self.assertEqual(self.tasks.get_task(root["task_id"])["description"], original["description"])

    def test_triage_cannot_rewrite_acceptance_or_change_roles(self):
        root = self.root()
        triage = self.triage(root)
        rewritten = self.result()
        rewritten["acceptance"] = ["Treat the report as completed implementation"]
        with self.assertRaises(PublicationRejected):
            self.apply(triage, rewritten)
        changed = self.apply(triage, self.result(role="sre"))
        self.assertEqual(changed["status"], "controller_scope_review")
        self.assertIsNone(self.tasks.get_task("REPAIR-" + root["id"]))

    def test_original_spec_change_since_triage_requires_controller_review(self):
        root = self.root()
        triage = self.triage(root)
        with self.tasks._connection(write=True) as conn:
            conn.execute("UPDATE tasks SET acceptance=? WHERE id=?", (json.dumps(["Changed specification"]), root["task_id"]))
        self.assertEqual(self.apply(triage)["status"], "controller_scope_review")
        self.assertIsNone(self.tasks.get_task("REPAIR-" + root["id"]))

    def test_source_resumed_while_triage_ran_prevents_repair_assignment(self):
        for status in ("ready", "running", "done"):
            root = self.root("resumed-" + status)
            triage = self.triage(root)
            with self.tasks._connection(write=True) as conn:
                conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, root["task_id"]))
            self.assertEqual(self.apply(triage)["status"], "controller_scope_review")
            self.assertIsNone(self.tasks.get_task("REPAIR-" + root["id"]))

    def test_repeated_triage_application_creates_only_one_repair(self):
        root = self.root()
        triage = self.triage(root)
        first = self.apply(triage)
        self.assertEqual(self.apply(triage), first)
        for _ in range(3):
            scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(len(self.autonomy.list_cycles()), 3)
        self.assertEqual(len(self.tasks.snapshot()["tasks"]), 2)

    def test_repeat_application_reconciles_repair_created_before_context_and_link_write(self):
        root = self.root()
        triage = self.triage(root)
        original_create = self.autonomy.update_cycle
        interrupted = {"raised": False}

        def interrupt_context(cycle_id, phase=None, **data):
            if data.get("recovery_kind") == "repair" and not interrupted["raised"]:
                interrupted["raised"] = True
                raise RuntimeError("Simulated controller interruption before repair context write")
            return original_create(cycle_id, phase=phase, **data)

        self.autonomy.update_cycle = interrupt_context
        with self.assertRaises(RuntimeError):
            self.apply(triage)
        self.autonomy.update_cycle = original_create
        result = self.apply(triage)
        repaired = self.autonomy.get_cycle(result["cycle_id"])
        self.assertEqual(repaired["recovery_kind"], "repair")
        self.assertEqual(repaired["source_task_acceptance"], triage["source_task_acceptance"])
        self.assertEqual(self.autonomy.get_cycle(triage["id"])["phase"], "done")
        self.assertEqual(len(self.autonomy.list_cycles()), 3)

    def test_explicit_escalation_has_controller_owner_and_no_followup(self):
        root = self.root()
        triage = self.triage(root)
        self.assertEqual(self.apply(triage, self.result(action="escalate"))["status"], "escalated")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(len(self.autonomy.list_cycles()), 2)
        root = self.autonomy.get_cycle(root["id"])
        self.assertEqual(root["recovery_owner"], "controller")
        self.assertEqual(root["recovery_status"], "escalated")
        self.assertEqual(root["recovery_diagnosis"], self.result()["diagnosis"])

    def test_cached_handoff_stops_when_parent_is_already_owned_or_resolved(self):
        for status in ("escalated", "controller_scope_review", "resolved"):
            root = self.root("owned-" + status)
            triage = self.triage(root)
            triage = self.autonomy.update_cycle(triage["id"], phase="triage_handoff", triage_result=self.result())
            self.autonomy.update_cycle(root["id"], recovery_status=status)
            self.assertEqual(self.apply(triage)["status"], status)
            self.assertEqual(self.autonomy.get_cycle(triage["id"])["phase"], "done")
            self.assertIsNone(self.tasks.get_task("REPAIR-" + root["id"]))

    def test_conflicting_existing_repair_task_ends_cached_handoff(self):
        root = self.root()
        triage = self.triage(root)
        triage = self.autonomy.update_cycle(triage["id"], phase="triage_handoff", triage_result=self.result())
        self.tasks.seed([{"id": "REPAIR-" + root["id"], "role": "engineer", "title": "Unrelated task",
                          "description": "A different existing task must not be adopted as this recovery.",
                          "acceptance": ["A different acceptance"]}])
        self.assertEqual(self.apply(triage)["status"], "escalated")
        self.assertEqual(self.autonomy.get_cycle(triage["id"])["phase"], "done")
        self.assertEqual(len(self.autonomy.list_cycles()), 2)

    def test_interrupted_triage_escalates_without_retry_or_refund(self):
        root = self.root()
        triage = self.triage(root)
        self.autonomy.reserve_attempt(triage["id"], "triage:0", 180,
                                      {"max_daily_seconds": 600, "max_daily_attempts": 3})
        self.autonomy.reconcile_interrupted()
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "escalated")
        attempt = self.autonomy.list_attempts()[0]
        self.assertEqual(attempt["status"], "interrupted")
        self.assertEqual(attempt["charged_seconds"], 180)
        self.assertEqual(len(self.autonomy.list_cycles()), 2)

    def test_failed_repair_escalates_and_does_not_generate_recovery_of_recovery(self):
        root = self.root()
        repair = self.apply(self.triage(root))
        self.autonomy.update_cycle(repair["cycle_id"], phase="needs_review",
                                   pr_url="https://github.com/example/project/pull/9", last_error="Bounded repair failed")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "escalated")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(len(self.autonomy.list_cycles()), 3)
        self.assertEqual(len(self.tasks.snapshot()["tasks"]), 2)

    def test_merged_repair_awaits_original_acceptance_reconciliation(self):
        root = self.root()
        repair = self.apply(self.triage(root))
        self.autonomy.update_cycle(repair["cycle_id"], phase="done", reviewed_sha="c" * 40,
                                   review={"verdict": "approve"}, ci_status="passed")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        root = self.autonomy.get_cycle(root["id"])
        self.assertEqual(root["recovery_status"], "repair_merged")
        self.assertEqual(root["recovery_owner"], "controller")
        self.assertEqual(self.tasks.get_task(root["task_id"])["status"], "blocked")
        self.assertEqual(root["phase"], "needs_review")

    def test_verified_partial_resolution_can_resume_after_store_completion(self):
        root = self.root()
        repair = self.apply(self.triage(root))
        replacement_url = "https://github.com/example/project/pull/9"
        self.autonomy.update_cycle(repair["cycle_id"], phase="done", pr_url=replacement_url)
        self.autonomy.update_cycle(root["id"], recovery_status="repair_merged")
        with self.tasks._connection(write=True) as conn:
            conn.execute("UPDATE tasks SET status='done',summary=? WHERE id=?",
                         ("Original acceptance satisfied by reviewed replacement " + replacement_url, root["task_id"]))
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        current = self.autonomy.get_cycle(root["id"])
        self.assertEqual(current["recovery_status"], "repair_merged")
        self.assertEqual(current["recovery_owner"], "controller")
        self.assertEqual(len(self.autonomy.list_cycles()), 3)
        self.assertEqual(self.autonomy.list_attempts(), [])
        # The exact local completion marker alone cannot stand in for its
        # durable source-to-triage-to-repair links.
        self.autonomy.update_cycle(root["id"], recovery_repair_cycle_id="unrelated")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "controller_scope_review")

    def test_sre_repair_governance_handoff_does_not_escalate_as_failure(self):
        root = self.root(role="sre")
        repair = self.apply(self.triage(root), self.result(role="sre"))
        self.autonomy.update_cycle(repair["cycle_id"], phase="needs_review", head_sha="d" * 40,
                                   reviewed_sha="d" * 40, review={"verdict": "approve"}, ci_status="passed",
                                   governance_status="awaiting_controller_integration")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "awaiting_controller_integration")
        self.assertEqual(len(self.autonomy.list_cycles()), 3)

    def test_resolved_root_is_terminal_for_scans_and_decision_replay(self):
        root = self.root()
        triage = self.triage(root)
        repair = self.apply(triage)
        self.autonomy.update_cycle(repair["cycle_id"], phase="done")
        self.autonomy.update_cycle(root["id"], recovery_status="resolved", recovery_owner="controller")
        events = len(self.tasks.snapshot()["events"])
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.apply(triage)["status"], "resolved")
        self.assertEqual(self.autonomy.get_cycle(root["id"])["recovery_status"], "resolved")
        self.assertEqual(len(self.tasks.snapshot()["events"]), events)

    def test_malformed_or_private_triage_output_is_rejected(self):
        root = self.root()
        triage = self.triage(root)
        invalid = ["not JSON", [], dict(self.result(), action={}), dict(self.result(), role=[]),
                   dict(self.result(), diagnosis="x" * 3001), dict(self.result(), repair_description="short"),
                   dict(self.result(), diagnosis="Read " + PRIVATE_PATH + "log.txt")]
        for payload in invalid:
            with self.subTest(payload=type(payload).__name__):
                with self.assertRaises(PublicationRejected):
                    self.apply(triage, payload)
        self.assertEqual(len(self.autonomy.list_cycles()), 2)

    def test_source_snapshot_is_detached_and_triage_is_bound_to_root(self):
        root = self.root()
        triage = self.triage(root)
        triage["source_task_acceptance"].append("Weakened copy")
        self.assertNotIn("Weakened copy", self.autonomy.get_cycle(triage["id"])["source_task_acceptance"])
        wrong = copy.deepcopy(triage)
        wrong["task_id"] = "TRIAGE-other"
        with self.assertRaises(PublicationRejected):
            self.apply(wrong)


if __name__ == "__main__":
    unittest.main()
