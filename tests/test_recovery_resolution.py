"""Recovery must finish original work without certifying its rejected PR head."""

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from colony.github_broker import GitHubBroker, PublicationRejected
from colony.store import Store


SOURCE_SHA = "a" * 40
REPLACEMENT_URL = "https://github.com/example/repo/pull/12"


class SupersededPullRequestTests(unittest.TestCase):
    def setUp(self):
        self.broker = GitHubBroker(".", {"repository": "example/repo"})
        self.remote = {
            "number": 5, "url": "https://github.com/example/repo/pull/5",
            "state": "OPEN", "headRefOid": SOURCE_SHA, "mergedAt": None,
        }
        self.comments = []
        self.mutations = []
        self.after_close = None
        self.before_comments = None
        self.lose_close_response = False
        self.broker.get_pr = Mock(side_effect=lambda number: copy.deepcopy(self.remote))
        self.broker.gh = Mock(side_effect=self.github)

    def github(self, *arguments):
        if arguments[0] == "api":
            if arguments[1] == "user":
                return json.dumps({"login": "controller"})
            if self.before_comments:
                self.before_comments()
            return json.dumps([self.comments] if "--slurp" in arguments else self.comments)
        if arguments[:2] == ("pr", "comment"):
            body = Path(arguments[arguments.index("--body-file") + 1]).read_text()
            self.comments.append({"body": body, "user": {"login": "controller"}})
            self.mutations.append("comment")
            return ""
        if arguments[:2] == ("pr", "close"):
            self.mutations.append("close")
            self.remote["state"] = "CLOSED"
            if self.after_close:
                self.after_close()
            if self.lose_close_response:
                self.lose_close_response = False
                raise subprocess.TimeoutExpired(["gh", "pr", "close"], 120)
            return ""
        raise AssertionError("Unexpected GitHub operation: %r" % (arguments,))

    def resolve(self):
        return self.broker.close_superseded_pr(5, SOURCE_SHA, REPLACEMENT_URL, "recovery-1")

    def test_comment_and_close_are_reconciled_without_duplicate_writes(self):
        self.assertEqual(self.resolve()["state"], "CLOSED")
        self.assertIn(REPLACEMENT_URL, self.comments[0]["body"])
        self.assertIn(SOURCE_SHA, self.comments[0]["body"])
        self.assertNotIn("Verdict: **approve**", self.comments[0]["body"])
        self.assertEqual(self.mutations, ["comment", "close"])
        self.assertEqual(self.resolve()["state"], "CLOSED")
        self.assertEqual(self.mutations, ["comment", "close"])

    def test_changed_source_head_never_gets_a_superseded_comment_or_close(self):
        self.remote["headRefOid"] = "b" * 40
        with self.assertRaises(PublicationRejected):
            self.resolve()
        self.assertEqual(self.mutations, [])

    def test_source_merged_outside_recovery_is_not_closed_or_certified(self):
        self.remote.update(state="MERGED", mergedAt="2026-10-21T10:00:00Z")
        with self.assertRaises(PublicationRejected):
            self.resolve()
        self.assertEqual(self.mutations, [])

    def test_unrelated_closed_source_is_not_treated_as_our_completed_write(self):
        self.remote["state"] = "CLOSED"
        with self.assertRaises(PublicationRejected):
            self.resolve()
        self.assertEqual(self.mutations, [])

    def test_another_author_cannot_forge_a_completed_closure_marker(self):
        self.remote["state"] = "CLOSED"
        self.comments.append({
            "body": ("<!-- colony-superseded:recovery-1:%s -->\n%s" %
                     (SOURCE_SHA, REPLACEMENT_URL)),
            "user": {"login": "another-account"},
        })
        with self.assertRaises(PublicationRejected):
            self.resolve()
        self.assertEqual(self.mutations, [])

    def test_a_marker_for_another_replacement_does_not_confirm_our_closure(self):
        self.remote["state"] = "CLOSED"
        self.comments.append({
            "body": ("<!-- colony-superseded:recovery-1:%s -->\n"
                     "https://github.com/example/repo/pull/99" % SOURCE_SHA),
            "user": {"login": "controller"},
        })
        with self.assertRaises(PublicationRejected):
            self.resolve()
        self.assertEqual(self.mutations, [])

    def test_replacement_url_prefix_is_not_an_exact_recovery_marker(self):
        self.remote["state"] = "CLOSED"
        self.comments.append({
            "body": ("<!-- colony-superseded:recovery-1:%s -->\n%s3" %
                     (SOURCE_SHA, REPLACEMENT_URL)),
            "user": {"login": "controller"},
        })
        with self.assertRaises(PublicationRejected):
            self.resolve()
        self.assertEqual(self.mutations, [])

    def test_source_head_changed_during_comment_fetch_is_rechecked_before_writes(self):
        self.before_comments = lambda: self.remote.update(headRefOid="b" * 40)
        with self.assertRaises(PublicationRejected):
            self.resolve()
        self.assertEqual(self.mutations, [])

    def test_source_cannot_be_its_own_replacement(self):
        with self.assertRaises(PublicationRejected):
            self.broker.close_superseded_pr(5, SOURCE_SHA, self.remote["url"], "recovery-1")
        self.assertEqual(self.mutations, [])

    def test_lost_close_response_is_safe_to_retry(self):
        self.lose_close_response = True
        try:
            self.resolve()
        except subprocess.TimeoutExpired:
            pass
        self.assertEqual(self.resolve()["state"], "CLOSED")
        self.assertEqual(self.mutations, ["comment", "close"])

    def test_head_change_during_close_cannot_confirm_source_completion(self):
        self.after_close = lambda: self.remote.update(headRefOid="b" * 40)
        with self.assertRaises(PublicationRejected):
            self.resolve()


class RecoveryTaskCompletionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Store(Path(directory.name) / "state.db").initialize()
        self.description = "Prove the unchanged original claim and preserve its assumptions."
        self.acceptance = ["Original theorem checked", "Invalid cases rejected"]
        self.store.seed([
            {"id": "SOURCE", "title": "Original task", "role": "researcher",
             "status": "failed", "description": self.description, "acceptance": self.acceptance},
            {"id": "REPAIR", "title": "Fresh bounded repair", "role": "researcher",
             "status": "done", "description": self.description, "acceptance": self.acceptance,
             "depends_on": []},
            {"id": "DEPENDENT", "title": "Dependent original work", "role": "engineer",
             "depends_on": ["SOURCE"]},
        ])
        self.store.set_task_artifacts("SOURCE", branch="codex/original",
                                      pr_url="https://github.com/example/repo/pull/5")
        self.store.set_task_artifacts("REPAIR", branch="codex/repair", pr_url=REPLACEMENT_URL)

    def complete(self):
        return self.store.complete_recovery(
            "SOURCE", "REPAIR", self.description, self.acceptance, REPLACEMENT_URL)

    def change(self, task_id, field, value):
        # Fixture-only corruption verifies that resolution fails closed.
        with self.store._connection(write=True) as connection:
            connection.execute("UPDATE tasks SET %s=? WHERE id=?" % field,
                               (json.dumps(value) if field == "acceptance" else value, task_id))

    def test_original_completes_once_and_releases_original_dependencies(self):
        original = self.complete()
        self.assertEqual(original["status"], "done")
        self.assertEqual(original["pr_url"], "https://github.com/example/repo/pull/5")
        self.assertEqual(original["description"], self.description)
        self.assertEqual(original["acceptance"], self.acceptance)
        self.assertEqual(self.store.get_task("DEPENDENT")["status"], "ready")
        events = self.store.snapshot()["events"]
        completion = [event for event in events if event["kind"] == "task.recovery_completed"]
        self.assertEqual(len(completion), 1)
        self.assertIn(REPLACEMENT_URL, json.dumps(completion[0]))
        self.assertIn("REPAIR", json.dumps(completion[0]))
        count = len(events)
        self.complete()
        self.assertEqual(len(self.store.snapshot()["events"]), count)

    def test_unfinished_repair_cannot_release_dependencies(self):
        self.change("REPAIR", "status", "review")
        with self.assertRaises((ValueError, PermissionError)):
            self.complete()
        self.assertEqual(self.store.get_task("SOURCE")["status"], "failed")
        self.assertEqual(self.store.get_task("DEPENDENT")["status"], "blocked")

    def test_controller_instructions_can_follow_the_unmodified_original_description(self):
        self.change("REPAIR", "description", self.description + "\nController repair diagnosis and bounds.")
        self.assertEqual(self.complete()["status"], "done")

    def test_changed_execution_role_cannot_complete_original_work(self):
        self.change("REPAIR", "role", "engineer")
        with self.assertRaises((ValueError, PermissionError)):
            self.complete()
        self.assertEqual(self.store.get_task("SOURCE")["status"], "failed")

    def test_existing_completion_by_another_action_is_not_overwritten(self):
        self.change("SOURCE", "status", "done")
        self.change("SOURCE", "summary", "Completed independently by another action")
        with self.assertRaises((ValueError, PermissionError)):
            self.complete()
        self.assertEqual(self.store.get_task("SOURCE")["summary"], "Completed independently by another action")

    def test_source_or_repair_specification_change_blocks_completion(self):
        for task_id, field, value in [
            ("SOURCE", "description", "A different claim"),
            ("SOURCE", "acceptance", list(reversed(self.acceptance))),
            ("REPAIR", "description", "A narrowed implementation proposal"),
            ("REPAIR", "acceptance", ["Only write a plan"]),
        ]:
            with self.subTest(task_id=task_id, field=field):
                self.change(task_id, field, value)
                with self.assertRaises((ValueError, PermissionError)):
                    self.complete()
                self.assertEqual(self.store.get_task("SOURCE")["status"], "failed")
                self.assertEqual(self.store.get_task("DEPENDENT")["status"], "blocked")
                self.change(task_id, field, self.acceptance if field == "acceptance" else self.description)

    def test_repair_url_must_match_the_completed_repair_artifact(self):
        self.store.set_task_artifacts("REPAIR", pr_url="https://github.com/example/repo/pull/99")
        with self.assertRaises((ValueError, PermissionError)):
            self.complete()
        self.assertEqual(self.store.get_task("SOURCE")["status"], "failed")

    def test_active_source_lease_cannot_be_completed_by_another_job(self):
        self.change("SOURCE", "status", "running")
        with self.assertRaises((ValueError, PermissionError)):
            self.complete()
        self.assertEqual(self.store.get_task("SOURCE")["status"], "running")


if __name__ == "__main__":
    unittest.main()
