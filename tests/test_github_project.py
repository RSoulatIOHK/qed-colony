import importlib.util
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock


SPEC = importlib.util.spec_from_file_location(
    "github_project_sync", Path(__file__).resolve().parents[1] / "scripts" / "sync_github_project.py")
board = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(board)


def pr(**values):
    return dict({"id": "PR1", "url": "https://github.com/example/repo/pull/1", "kind": "pr",
                 "state": "OPEN", "title": "T1: Work", "headRefOid": "abc", "comments": {"nodes": []}}, **values)


class ProjectMappingTests(unittest.TestCase):
    def test_closed_original_is_done_only_with_exact_resolved_recovery_evidence(self):
        item = pr(state="CLOSED", merged=False, headRefOid="a" * 40)
        state = {"tasks": [{"id": "T1", "status": "done", "pr_url": item["url"]}],
                 "autonomy": {"cycles": [{"task_id": "T1", "phase": "needs_review",
                     "pr_url": item["url"], "source_pr_url": item["url"],
                     "recovery_status": "resolved", "source_head_sha": "a" * 40,
                     "recovery_replacement_pr_url": "https://github.com/example/repo/pull/2"}]}}
        result = board.desired_items([], [item], state)[0]
        self.assertEqual(result["lane"], "Done")
        self.assertIn("replacement", result["reason"])
        self.assertEqual(board.desired_items([], [item])[0]["lane"], "Blocked")
        mutations = [
            ("task", "status", "blocked"),
            ("task", "pr_url", "https://github.com/example/repo/pull/99"),
            ("cycle", "pr_url", "https://github.com/example/repo/pull/99"),
            ("cycle", "source_pr_url", "https://github.com/example/repo/pull/99"),
            ("cycle", "source_pr_url", None),
            ("cycle", "recovery_status", "repair_merged"),
            ("cycle", "source_head_sha", "b" * 40),
            ("cycle", "source_head_sha", None),
            ("cycle", "recovery_replacement_pr_url", item["url"]),
            ("cycle", "recovery_replacement_pr_url", "https://github.com/another/repo/pull/2"),
            ("cycle", "recovery_replacement_pr_url", None),
        ]
        for kind, field, value in mutations:
            altered = copy.deepcopy(state)
            target = altered["tasks"][0] if kind == "task" else altered["autonomy"]["cycles"][0]
            target[field] = value
            with self.subTest(kind=kind, field=field, value=value):
                self.assertEqual(board.desired_items([], [item], altered)[0]["lane"], "Blocked")
        # A replacement does not complete an original PR reopened by somebody else.
        item["state"] = "OPEN"
        self.assertNotEqual(board.desired_items([], [item], state)[0]["lane"], "Done")

    def test_github_terminal_states_are_honest(self):
        self.assertEqual(board.pr_lane(pr(state="MERGED", merged=True))[0], "Done")
        self.assertEqual(board.pr_lane(pr(state="CLOSED", merged=False))[0], "Blocked")
        issue = {"state": "CLOSED"}
        self.assertEqual(board.issue_lane(issue, [])[0], "Done")
        issue["state"] = "OPEN"
        self.assertEqual(board.issue_lane(issue, [pr(state="MERGED", merged=True)])[0], "Todo")

    def test_draft_review_failure_conflict_and_check_failure(self):
        self.assertEqual(board.pr_lane(pr(isDraft=True))[0], "In progress")
        self.assertEqual(board.pr_lane(pr())[0], "In review")
        for item in [pr(reviewDecision="CHANGES_REQUESTED"), pr(mergeable="CONFLICTING"),
                     pr(commits={"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]})]:
            self.assertEqual(board.pr_lane(item)[0], "Blocked")

    def test_model_review_requires_controller_and_exact_current_head(self):
        item = pr(comments={"nodes": [{"author": {"login": "controller"},
                  "body": "Verdict: **changes_requested**\n<!-- colony-review:cycle:abc -->"}]})
        self.assertEqual(board.pr_lane(item, "controller")[0], "Blocked")
        self.assertEqual(board.pr_lane(item, "another-account")[0], "In review")
        item["comments"]["nodes"][0]["body"] = "Verdict: **reject**\n<!-- colony-review:cycle:abc -->"
        self.assertEqual(board.pr_lane(item, "controller")[0], "Blocked")
        item["headRefOid"] = "def"
        self.assertEqual(board.pr_lane(item, "controller")[0], "In review")

    def test_linked_issue_and_explicit_labels(self):
        issue = {"state": "OPEN", "labels": {"nodes": [{"name": "ready"}]}}
        self.assertEqual(board.issue_lane(issue, [])[0], "Ready")
        issue["labels"]["nodes"] = []
        self.assertEqual(board.issue_lane(issue, [pr(isDraft=True)])[0], "In progress")
        self.assertEqual(board.issue_lane(issue, [pr(reviewDecision="CHANGES_REQUESTED")])[0], "Blocked")

    def test_fresh_cycle_blockers_and_governance_hold(self):
        state = {"tasks": [{"id": "T1", "status": "review"}],
                 "autonomy": {"cycles": [{"task_id": "T1", "phase": "needs_review"}]}}
        self.assertEqual(board.desired_items([], [pr()], state)[0]["lane"], "Blocked")
        state["autonomy"]["cycles"][0]["governance_status"] = "awaiting_controller_integration"
        result = board.desired_items([], [pr()], state)[0]
        self.assertEqual(result["lane"], "Blocked")
        self.assertIn("controller integration", result["reason"])

    def test_budget_limit_does_not_mislabel_a_running_reservation(self):
        state = {"tasks": [{"id": "T1", "status": "running"}],
                 "autonomy": {"cycles": [{"task_id": "T1", "phase": "authoring"}],
                              "budget": {"exhausted": True}, "service": {"status": "working"}}}
        self.assertEqual(board.recorded_lane(pr(), state)[0], "In progress")
        state["autonomy"]["service"]["status"] = "budget_limited"
        self.assertEqual(board.recorded_lane(pr(), state)[0], "Blocked")

    def test_local_done_never_completes_an_open_item_or_overrides_github_failure(self):
        state = {"tasks": [{"id": "T1", "status": "done"}]}
        self.assertEqual(board.desired_items([], [pr()], state)[0]["lane"], "In review")
        self.assertEqual(board.desired_items([], [pr(state="MERGED")], state)[0]["lane"], "Done")
        self.assertEqual(board.desired_items([], [pr(reviewDecision="CHANGES_REQUESTED")], state)[0]["lane"], "Blocked")

    def test_task_matches_exact_identifier_not_a_substring(self):
        state = [{"id": "T1", "status": "running"}, {"id": "T10", "status": "blocked"}]
        self.assertEqual(board.task_for_item(pr(title="T10: Other"), state)["id"], "T10")
        self.assertIsNone(board.task_for_item(pr(title="Unrelated T1 example"), state))


class ProjectSyncTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.project = {"id": "P", "status_field": "F", "viewerCanUpdate": True,
                        "options": {lane: str(i) for i, lane in enumerate(board.LANES)}}
        self.desired = [{"content_id": "PR1", "lane": "In review", "url": pr()["url"], "reason": "open"}]

    def test_dry_run_never_mutates(self):
        self.assertEqual(board.sync(self.api, self.project, self.desired, {})[0]["action"], "add")
        self.api.graphql.assert_not_called()

    def test_add_then_update_and_repeat_is_idempotent(self):
        self.api.graphql.side_effect = [{"addProjectV2ItemById": {"item": {"id": "ITEM1"}}}, {}]
        existing = {}
        board.sync(self.api, self.project, self.desired, existing, apply=True)
        self.assertEqual(self.api.graphql.call_count, 2)
        self.api.graphql.reset_mock()
        self.assertEqual(board.sync(self.api, self.project, self.desired, existing, apply=True), [])
        self.api.graphql.assert_not_called()

    def test_update_existing_item_does_not_add_duplicate(self):
        existing = {"PR1": {"id": "ITEM1", "fieldValueByName": {"optionId": "0"}}}
        board.sync(self.api, self.project, self.desired, existing, apply=True)
        self.api.graphql.assert_called_once_with(board.SET_STATUS, project="P", item="ITEM1", field="F", option="3")

    def test_insufficient_permission_stops_before_writes(self):
        self.project["viewerCanUpdate"] = False
        with self.assertRaises(board.SyncError):
            board.sync(self.api, self.project, self.desired, {}, apply=True)
        self.api.graphql.assert_not_called()

    def test_project_visibility_and_schema_validated_before_writes(self):
        for project in [{"public": False}, {"public": True, "closed": True},
                        {"public": True, "closed": False, "field": {"id": "F", "options": []}}]:
            self.api.graphql.return_value = {"user": {"projectV2": project}}
            with self.assertRaises(board.SyncError):
                board.load_project(self.api, "owner", 1, "user")
        self.assertTrue(all("query" in call.args[0] for call in self.api.graphql.call_args_list))

    def test_urls_reject_credentials_arbitrary_hosts_and_nonproject_paths(self):
        self.assertEqual(board.project_reference("https://github.com/users/example/projects/2"), ("example", 2, "user"))
        for url in ["http://github.com/users/example/projects/2", "https://evil.test/users/example/projects/2",
                    "https://github.com@example.test/users/example/projects/2", "https://github.com/example/repo"]:
            with self.assertRaises(board.SyncError):
                board.project_reference(url)
        for url in ["http://example.test/api/state", "http://localhost/api/state", "http://127.0.0.1/elsewhere",
                    "http://user@127.0.0.1/api/state", "http://127.0.0.1/api/state?redirect=x"]:
            with self.assertRaises(board.SyncError):
                board.local_state(url)

    def test_stale_naive_or_malformed_state_is_not_used(self):
        for state in [{}, {"generated_at": "2000-01-01T00:00:00Z"},
                      {"generated_at": "2026-10-21T00:00:00"},
                      {"generated_at": "2026-10-21T00:00:00Z", "tasks": "not a list"}]:
            with self.assertRaises(board.SyncError):
                board.validate_state(state)

    def test_repository_and_project_reads_follow_every_page(self):
        self.api.graphql.side_effect = [
            {"repository": {"issues": {"nodes": [{"id": "I1"}],
              "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"}}}},
            {"repository": {"issues": {"nodes": [{"id": "I2"}],
              "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
            {"node": {"items": {"nodes": [{"id": "P1", "content": {"id": "I1"}}],
              "pageInfo": {"hasNextPage": True, "endCursor": "cursor2"}}}},
            {"node": {"items": {"nodes": [{"id": "P2", "content": None}],
              "pageInfo": {"hasNextPage": False, "endCursor": None}}}},
        ]
        self.assertEqual([item["id"] for item in board.repository_items(self.api, "owner", "repo", "issues")], ["I1", "I2"])
        self.assertEqual(set(board.project_items(self.api, "P")), {"I1"})
        self.assertEqual(self.api.graphql.call_args_list[1].kwargs["cursor"], "cursor1")
        self.assertEqual(self.api.graphql.call_args_list[3].kwargs["cursor"], "cursor2")

    def test_private_repository_is_rejected_before_public_board_writes(self):
        self.api.graphql.return_value = {"repository": {"isPrivate": True}}
        with self.assertRaises(board.SyncError):
            board.repository_items(self.api, "owner", "repo", "issues")


if __name__ == "__main__":
    unittest.main()
