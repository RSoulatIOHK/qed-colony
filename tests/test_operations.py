import json
from pathlib import Path
import tempfile
import unittest

from colony.autonomy_store import AutonomyStore
from colony.github_broker import PublicationRejected
from colony.operations import (enqueue_followups, maybe_enqueue_audit,
                               parse_operations_output, render_operations_report)
from colony.store import Store


def payload(count=1):
    return {"report": "Observed a repeated review handoff delay; inspect recorded CI evidence.",
            "role_proposals": ["Release steward: propose release checklists; no deployment authority."],
            "follow_up_tasks": [{"title": "Inspect review delay %d" % index, "role": "sre",
                                 "description": "Measure and fix the bounded review handoff delay.",
                                 "acceptance": ["Fault injection reproduces and verifies the fix"]}
                                for index in range(count)]}


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.db"
        self.tasks = Store(self.path).initialize()
        self.autonomy = AutonomyStore(self.path).initialize()
        self.policy = {"operations_audit_every_cycles": 3}

    def completed(self, count, role="engineer", prefix="T"):
        for number in range(count):
            cycle = self.autonomy.create_cycle(prefix + str(number), role)
            self.autonomy.update_cycle(cycle["id"], phase="done", private_log="/Users/private/log.txt")

    def test_periodic_audit_threshold_idempotency_and_one_pending(self):
        self.completed(2)
        self.assertIsNone(maybe_enqueue_audit(self.tasks, self.autonomy, self.policy))
        self.completed(3)
        first = maybe_enqueue_audit(self.tasks, self.autonomy, self.policy)
        self.assertEqual(first["id"], "OPS001")
        self.assertEqual(first["role"], "operations")
        self.assertEqual(first["priority"], 125)
        self.assertEqual(self.autonomy.list_attempts(), [])
        self.assertIsNone(maybe_enqueue_audit(self.tasks, self.autonomy, self.policy))
        self.completed(6)
        self.assertIsNone(maybe_enqueue_audit(self.tasks, self.autonomy, self.policy))
        self.tasks.transition("OPS001", "failed", "test")
        second = maybe_enqueue_audit(self.tasks, self.autonomy, self.policy)
        self.assertEqual(second["id"], "OPS002")

    def test_planner_and_own_audits_do_not_trigger_more_audits(self):
        self.completed(10, "planner", "P")
        self.completed(10, "operations", "O")
        self.assertIsNone(maybe_enqueue_audit(self.tasks, self.autonomy, self.policy))
        self.completed(3)
        self.assertEqual(maybe_enqueue_audit(self.tasks, self.autonomy, self.policy)["id"], "OPS001")

    def test_manual_first_audit_prevents_duplicate_batch(self):
        self.tasks.seed([{"id": "OPS001", "title": "Initial audit", "role": "operations", "status": "done"}])
        self.completed(3)
        self.assertIsNone(maybe_enqueue_audit(self.tasks, self.autonomy, self.policy))
        self.completed(6)
        self.assertEqual(maybe_enqueue_audit(self.tasks, self.autonomy, self.policy)["id"], "OPS002")

    def test_disable_and_public_evidence_omit_private_context_and_secrets(self):
        self.completed(3)
        self.assertIsNone(maybe_enqueue_audit(self.tasks, self.autonomy, {"operations_audit_every_cycles": 0}))
        self.tasks.seed([{"id": "badtitle", "title": "/Users/private/project key ghp_" + "a" * 30, "role": "researcher"}])
        audit = maybe_enqueue_audit(self.tasks, self.autonomy, self.policy)
        self.assertNotIn("/Users/", audit["description"])
        self.assertNotIn("ghp_", audit["description"])
        self.assertNotIn("private_log", audit["description"])
        self.assertIn("<redacted operational text>", audit["description"])

    def test_structured_report_roundtrip_and_role_proposals_have_no_authority(self):
        parsed = parse_operations_output(json.dumps(payload(3)))
        self.assertEqual(len(parsed["follow_up_tasks"]), 3)
        report = render_operations_report(parsed)
        self.assertIn("grants no permissions", report)
        self.assertIn("Release steward", report)
        self.assertEqual(self.tasks.snapshot()["tasks"], [])
        parsed["follow_up_tasks"][0]["role"] = "admin"
        with self.assertRaises(PublicationRejected):
            parse_operations_output(parsed)

    def test_report_rejects_unbounded_output_secrets_new_roles_and_recursive_audits(self):
        invalid = []
        item = payload(); item["report"] = "x" * 12001; invalid.append(item)
        item = payload(); item["role_proposals"] *= 6; invalid.append(item)
        invalid.append(payload(4))
        for role in ("operations", "admin", "release_manager", ["engineer"]):
            item = payload(); item["follow_up_tasks"][0]["role"] = role; invalid.append(item)
        item = payload(); item["authority"] = "deploy"; invalid.append(item)
        item = payload(); item["report"] = "/Users/private/log.txt"; invalid.append(item)
        item = payload(); item["report"] = "ghp_" + "a" * 30; invalid.append(item)
        for item in invalid:
            with self.subTest(value=str(item)[:100]), self.assertRaises(PublicationRejected):
                parse_operations_output(item)

    def test_followups_are_bounded_idempotent_and_do_not_change_permissions(self):
        proposal = payload(3)
        ids = enqueue_followups(self.tasks, {"id": "cycle123"}, proposal, {"operations_max_backlog": 2})
        self.assertEqual(ids, ["OPSFOLLOW-cycle123-1", "OPSFOLLOW-cycle123-2"])
        self.assertEqual(enqueue_followups(self.tasks, {"id": "cycle123"}, proposal, {"operations_max_backlog": 2}), ids)
        tasks = self.tasks.snapshot()["tasks"]
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(task["role"] == "sre" and task["status"] == "ready" for task in tasks))
        self.assertEqual(self.autonomy.list_cycles(), [])

    def test_existing_ready_backlog_consumes_followup_capacity(self):
        self.tasks.seed([{"id": "existing", "title": "Existing work", "role": "engineer"}])
        self.assertEqual(enqueue_followups(self.tasks, {"id": "cycle"}, payload(3), {"operations_max_backlog": 1}), [])
        self.assertEqual(len(self.tasks.snapshot()["tasks"]), 1)


if __name__ == "__main__":
    unittest.main()
