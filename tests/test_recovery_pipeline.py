"""Exercise the real recovery and publication state machines with no network."""

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from colony.autonomy_store import AutonomyStore
from colony.github_broker import GitHubBroker
from colony.pipeline import Pipeline, REVIEW_SCHEMA
from colony.recovery import TRIAGE_SCHEMA, scan_recoveries
from colony.store import Store


def public_pr(number, sha):
    return {"number": number, "url": "https://github.com/example/repo/pull/%s" % number,
            "state": "OPEN", "mergedAt": None, "headRefOid": sha,
            "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
                                  for name in ("control-plane", "lean-seed")]}


class InMemoryGitHub(GitHubBroker):
    """Keep the real merge/close guards while replacing their transport."""

    def __init__(self, root):
        super().__init__(root, {"repository": "example/repo"})
        self.prs = {5: public_pr(5, "a" * 40)}
        self.comments = {5: [], 7: []}
        self.prepared = []
        self.merged = []
        self.closed = []

    def prepare_worktree(self, cycle):
        checkout = self.root / cycle["id"]
        checkout.mkdir(exist_ok=True)
        self.prepared.append(cycle["id"])
        return {"worktree": str(checkout), "branch": "codex/" + cycle["id"], "base_sha": "b" * 40}

    def validate_changes(self, *args):
        return ["research/recovery-result.md"]

    def commit(self, cycle, task):
        return "c" * 40

    def publish(self, cycle, task, summary):
        self.prs[7] = public_pr(7, cycle["head_sha"])
        return copy.deepcopy(self.prs[7])

    def get_pr(self, number):
        return copy.deepcopy(self.prs[number])

    def gh(self, *arguments):
        if arguments[:2] == ("api", "user"):
            return json.dumps({"login": "controller"})
        if arguments[0] == "api":
            endpoint = next(value for value in arguments if value.startswith("repos/"))
            number = int(re.search(r"/issues/([0-9]+)/comments", endpoint)[1])
            comments = self.comments[number]
            return json.dumps([comments] if "--slurp" in arguments else comments)
        number = int(arguments[2])
        if arguments[:2] == ("pr", "comment"):
            body = Path(arguments[arguments.index("--body-file") + 1]).read_text()
            self.comments[number].append({"body": body, "user": {"login": "controller"}})
            return ""
        if arguments[:2] == ("pr", "merge"):
            expected = arguments[arguments.index("--match-head-commit") + 1]
            if expected != self.prs[number]["headRefOid"]:
                raise AssertionError("Merge attempted against the wrong head")
            self.merged.append(number)
            self.prs[number].update(state="MERGED", mergedAt="2026-10-21T12:00:00Z")
            return ""
        if arguments[:2] == ("pr", "close"):
            self.closed.append(number)
            self.prs[number]["state"] = "CLOSED"
            return ""
        raise AssertionError("Unexpected transport operation: %r" % (arguments,))


class RecoveryPipelineTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.tasks = Store(self.root / "state.db").initialize()
        self.autonomy = AutonomyStore(self.tasks.path).initialize()
        self.policy = {"max_daily_seconds": 10000, "max_daily_attempts": 30,
                       "planner_timeout_seconds": 10, "author_timeout_seconds": 10,
                       "review_timeout_seconds": 10, "automatic_publication": True,
                       "automatic_merge": True, "max_revisions": 2}
        self.broker = InMemoryGitHub(self.root)
        self.jobs = []
        self.review_verdict = "approve"
        self.pipeline = Pipeline(self.root, self.tasks, self.autonomy, self.policy,
                                 broker=self.broker, executor=self.execute)

    def execute(self, root, worktree, prompt, timeout, sandbox, agent_id, **kwargs):
        schema = kwargs.get("output_schema")
        self.jobs.append({"schema": schema, "sandbox": sandbox, "prompt": prompt, "timeout": timeout})
        if schema == TRIAGE_SCHEMA:
            output = {"action": "repair", "diagnosis": "Correct the missing original case.",
                      "repair_title": "Repair the original acceptance failure",
                      "repair_description": "Reproduce the source work and correct its missing original case.",
                      "role": self.source_role}
        elif schema == REVIEW_SCHEMA:
            output = {"verdict": self.review_verdict, "summary": "Original acceptance assessed.",
                      "findings": [] if self.review_verdict == "approve" else ["An original case remains missing."]}
        else:
            output = "Implemented the original acceptance with a bounded correction."
        return {"status": "completed", "summary": json.dumps(output) if isinstance(output, dict) else output,
                "elapsed_seconds": 1, "usage": {"input_tokens": 5, "output_tokens": 5}}

    def source(self, role="engineer"):
        self.source_role = role
        self.tasks.seed([
            {"id": "ORIGINAL", "title": "Implement the original required behavior", "role": role,
             "description": "Implement the full original behavior without weakening its specification.",
             "acceptance": ["Original behavior works", "Invalid original case rejected"], "status": "blocked"},
            {"id": "DEPENDENT", "title": "Use the original verified result", "role": "engineer",
             "depends_on": ["ORIGINAL"]},
        ])
        self.tasks.set_task_artifacts("ORIGINAL", branch="codex/original", pr_url=self.broker.prs[5]["url"])
        root = self.autonomy.create_cycle("ORIGINAL", role)
        root = self.autonomy.update_cycle(root["id"], phase="needs_review", pr_number=5,
                    pr_url=self.broker.prs[5]["url"], head_sha="a" * 40, base_sha="e" * 40,
                    last_error="Revision limit reached after review requested an original case.")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.root_cycle = root
        return self.autonomy.get_cycle(self.autonomy.get_cycle(root["id"])["recovery_triage_cycle_id"])

    def step(self, cycle):
        return self.pipeline.advance(self.autonomy.get_cycle(cycle["id"]))

    def queued_repair(self, role="engineer"):
        triage = self.source(role)
        self.step(triage)
        current = self.autonomy.get_cycle(self.root_cycle["id"])
        return self.autonomy.get_cycle(current["recovery_repair_cycle_id"])

    def finish_repair(self, role="engineer"):
        repair = self.queued_repair(role)
        for _ in range(5):
            repair = self.step(repair)
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        return repair

    def test_recovery_runs_normal_gates_then_resolves_original_and_dependencies(self):
        repair = self.queued_repair()
        original = self.tasks.get_task("ORIGINAL")
        self.assertEqual(repair["phase"], "queued")
        self.assertEqual(self.tasks.get_task(repair["task_id"])["acceptance"], original["acceptance"])
        self.assertFalse(any(cycle["role"] == "operations" for cycle in self.autonomy.list_cycles()))
        for _ in range(5):
            repair = self.step(repair)
        self.assertEqual(repair["phase"], "done")
        self.assertEqual(repair["base_sha"], "b" * 40)
        self.assertEqual(repair["reviewed_sha"], repair["head_sha"])
        self.assertEqual(self.broker.merged, [7])
        self.assertEqual(self.broker.closed, [])
        self.assertEqual(self.tasks.get_task("ORIGINAL")["status"], "blocked")
        self.assertEqual([job["sandbox"] for job in self.jobs], ["read-only", "workspace-write", "read-only"])
        self.assertEqual(self.autonomy.get_budget(self.policy)["attempts"], 3)
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(self.autonomy.get_cycle(self.root_cycle["id"])["recovery_status"], "repair_merged")
        resolved = self.pipeline.reconcile_recovery(self.root_cycle["id"])
        self.assertEqual(resolved["recovery_status"], "resolved")
        self.assertEqual(resolved["phase"], "needs_review")
        self.assertIsNone(resolved.get("reviewed_sha"))
        self.assertEqual(self.broker.closed, [5])
        self.assertEqual(self.tasks.get_task("ORIGINAL")["status"], "done")
        self.assertEqual(self.tasks.get_task("DEPENDENT")["status"], "ready")
        self.assertIn(self.broker.prs[7]["url"], self.tasks.get_task("ORIGINAL")["summary"])
        events = len(self.tasks.snapshot()["events"])
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.pipeline.reconcile_recovery(self.root_cycle["id"])
        self.assertEqual(len(self.tasks.snapshot()["events"]), events)
        self.assertEqual(self.broker.closed, [5])

    def test_cached_triage_handoff_replays_after_budget_is_exhausted(self):
        triage = self.source()
        self.pipeline.policy["max_daily_attempts"] = 1
        with patch("colony.pipeline.apply_triage_result", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.step(triage)
        cached = self.autonomy.get_cycle(triage["id"])
        self.assertEqual(cached["phase"], "triage_handoff")
        self.assertEqual(self.autonomy.get_budget(self.pipeline.policy)["remaining_attempts"], 0)
        self.assertEqual(self.step(cached)["phase"], "done")
        self.assertEqual(len(self.jobs), 1)
        self.assertIsNotNone(self.tasks.get_task("REPAIR-" + self.root_cycle["id"]))

    def test_repair_changes_requested_escalates_without_another_generation(self):
        self.review_verdict = "changes_requested"
        repair = self.finish_repair()
        self.assertEqual(repair["phase"], "needs_review")
        self.assertEqual(repair.get("revision", 0), 0)
        self.assertEqual(self.autonomy.get_cycle(self.root_cycle["id"])["recovery_status"], "escalated")
        for _ in range(3):
            scan_recoveries(self.tasks, self.autonomy, self.policy)
        self.assertEqual(len(self.autonomy.list_cycles()), 3)
        self.assertEqual(len(self.jobs), 3)
        self.assertEqual(self.broker.closed, [])

    def assert_resolution_blocked(self, source_status="blocked"):
        self.assertEqual(self.pipeline.reconcile_recovery(self.root_cycle["id"])["recovery_status"], "escalated")
        self.assertEqual(self.broker.closed, [])
        self.assertEqual(self.tasks.get_task("ORIGINAL")["status"], source_status)
        self.assertEqual(self.tasks.get_task("DEPENDENT")["status"], "blocked")

    def test_active_source_is_rejected_before_remote_closure(self):
        self.finish_repair()
        with self.tasks._connection(write=True) as connection:
            connection.execute("UPDATE tasks SET status='running' WHERE id='ORIGINAL'")
        self.assert_resolution_blocked("running")

    def test_ready_source_is_rejected_before_remote_closure(self):
        self.finish_repair()
        with self.tasks._connection(write=True) as connection:
            connection.execute("UPDATE tasks SET status='ready' WHERE id='ORIGINAL'")
        self.assert_resolution_blocked("ready")

    def test_unrelated_source_completion_is_rejected_before_remote_closure(self):
        self.finish_repair()
        with self.tasks._connection(write=True) as connection:
            connection.execute("UPDATE tasks SET status='done',summary='Completed by another action' WHERE id='ORIGINAL'")
        self.assert_resolution_blocked("done")

    def test_verified_local_completion_replays_after_interruption_before_root_update(self):
        repair = self.finish_repair()
        source = self.tasks.get_task("ORIGINAL")
        task = self.tasks.get_task(repair["task_id"])
        # The controller stopped after its remote closure and atomic task write.
        self.broker.close_superseded_pr(5, "a" * 40, task["pr_url"], self.root_cycle["id"])
        self.tasks.complete_recovery("ORIGINAL", task["id"], source["description"], source["acceptance"], task["pr_url"])
        result = self.pipeline.reconcile_recovery(self.root_cycle["id"])
        self.assertEqual(result["recovery_status"], "resolved")
        self.assertEqual(self.broker.closed, [5])
        self.assertEqual(self.tasks.get_task("DEPENDENT")["status"], "ready")
        completions = [event for event in self.tasks.snapshot()["events"]
                       if event["kind"] == "task.recovery_completed"]
        self.assertEqual(len(completions), 1)

    def test_changed_original_acceptance_blocks_completion(self):
        self.finish_repair()
        with self.tasks._connection(write=True) as connection:
            connection.execute("UPDATE tasks SET acceptance=? WHERE id='ORIGINAL'", (json.dumps(["Altered claim"]),))
        self.assert_resolution_blocked()

    def test_changed_replacement_head_blocks_completion(self):
        self.finish_repair()
        self.broker.prs[7]["headRefOid"] = "d" * 40
        self.assert_resolution_blocked()

    def test_fresh_required_ci_failure_blocks_completion(self):
        self.finish_repair()
        self.broker.prs[7]["statusCheckRollup"][0]["conclusion"] = "FAILURE"
        self.assert_resolution_blocked()

    def test_changed_source_head_blocks_completion(self):
        self.finish_repair()
        self.broker.prs[5]["headRefOid"] = "d" * 40
        self.assert_resolution_blocked()

    def test_sre_repair_stops_at_separate_controller_integration(self):
        repair = self.finish_repair("sre")
        self.assertEqual(repair["phase"], "needs_review")
        self.assertEqual(repair["governance_status"], "awaiting_controller_integration")
        root = self.pipeline.reconcile_recovery(self.root_cycle["id"])
        self.assertEqual(root["recovery_status"], "awaiting_controller_integration")
        self.assertEqual(self.broker.merged, [])
        self.assertEqual(self.broker.closed, [])
        self.assertEqual(self.tasks.get_task("ORIGINAL")["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
