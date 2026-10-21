import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from colony.github_broker import GitHubBroker, PublicationRejected, checks_state, validate_public_text


def passing_pr(sha="a" * 40):
    return {"number": 7, "url": "https://github.com/example/repo/pull/7", "state": "OPEN",
            "headRefOid": sha, "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
                                  for name in ["control-plane", "lean-seed"]]}


class BrokerGateTests(unittest.TestCase):
    def test_ci_requires_every_check_and_rejects_duplicates_with_failure(self):
        pr = passing_pr()
        self.assertEqual(checks_state(pr, ["control-plane", "lean-seed"]), "passed")
        self.assertEqual(checks_state(pr, ["missing"]), "pending")
        pr["statusCheckRollup"].append({"name": "lean-seed", "status": "COMPLETED", "conclusion": "FAILURE"})
        self.assertEqual(checks_state(pr, ["control-plane", "lean-seed"]), "failed")

    def test_skipped_neutral_or_unfinished_checks_do_not_pass(self):
        for conclusion in ["SKIPPED", "NEUTRAL", None]:
            pr = passing_pr()
            pr["statusCheckRollup"][0]["conclusion"] = conclusion
            self.assertEqual(checks_state(pr, ["control-plane", "lean-seed"]), "pending")
        pr["statusCheckRollup"][0].update(status="IN_PROGRESS", conclusion="SUCCESS")
        self.assertEqual(checks_state(pr, ["control-plane", "lean-seed"]), "pending")

    def test_merge_rechecks_exact_head_and_required_ci(self):
        broker = GitHubBroker(".", {"repository": "example/repo"})
        pr = passing_pr()
        broker.get_pr = Mock(return_value=pr)
        broker.gh = Mock()
        with self.assertRaises(PublicationRejected):
            broker.merge(7, "b" * 40)
        broker.gh.assert_not_called()
        pr["statusCheckRollup"][0]["conclusion"] = "FAILURE"
        with self.assertRaises(PublicationRejected):
            broker.merge(7, "a" * 40)
        broker.gh.assert_not_called()

    def test_merge_uses_match_head_without_admin_override(self):
        broker = GitHubBroker(".", {"repository": "example/repo"})
        broker.get_pr = Mock(return_value=passing_pr())
        broker.gh = Mock()
        broker.merge(7, "a" * 40)
        broker.gh.assert_called_once_with("pr", "merge", "7", "--squash", "--match-head-commit", "a" * 40)

    def test_already_merged_other_head_is_rejected(self):
        broker = GitHubBroker(".")
        broker.get_pr = Mock(return_value=dict(passing_pr(), state="MERGED", mergedAt="now"))
        with self.assertRaises(PublicationRejected):
            broker.merge(7, "b" * 40)

    def test_publish_reuses_existing_pr_after_push(self):
        broker = GitHubBroker(".")
        existing = passing_pr()
        broker.git = Mock()
        broker.find_pr = Mock(return_value=existing)
        broker.gh = Mock()
        result = broker.publish({"worktree": ".", "branch": "codex/cycle", "id": "123"},
                                {"id": "T1", "title": "Example"}, "Measured result")
        self.assertEqual(result, existing)
        broker.gh.assert_not_called()
        broker.git.assert_called_once()

    def test_review_comment_is_idempotent_and_honestly_labelled(self):
        broker = GitHubBroker(".")
        broker.gh = Mock(return_value=json.dumps([{"body": "<!-- colony-review:c1:abc -->"}]))
        broker.comment_review(7, {"verdict": "approve", "summary": "Correct", "findings": []}, "abc", "c1")
        self.assertEqual(broker.gh.call_count, 1)

    def test_public_text_rejects_secrets_and_machine_paths(self):
        for value in ["/Users/someone/project/file", "ghp_" + "a" * 30, "-----BEGIN PRIVATE KEY-----"]:
            with self.assertRaises(PublicationRejected):
                validate_public_text(value)
        self.assertEqual(validate_public_text("lean/Colony/Tactic.lean"), "lean/Colony/Tactic.lean")


class BrokerPathTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.run_git("init", "-q")
        self.run_git("config", "user.email", "test@example.invalid")
        self.run_git("config", "user.name", "Test controller")
        for name in ["lean/Colony/Tactic.lean", "lean/Challenge.lean", "research/prior.md"]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("initial\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "initial")
        self.base = self.run_git("rev-parse", "HEAD")
        self.broker = GitHubBroker(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def run_git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def test_only_allowlisted_implementation_paths_publish(self):
        (self.root / "lean/Colony/Tactic.lean").write_text("changed\n")
        self.assertEqual(self.broker.validate_changes(self.root, "engineer", self.base), ["lean/Colony/Tactic.lean"])
        with self.assertRaises(PublicationRejected):
            self.broker.validate_changes(self.root, "researcher", self.base)

    def test_renaming_challenge_to_allowed_path_cannot_hide_protected_deletion(self):
        self.run_git("mv", "lean/Challenge.lean", "research/challenge.md")
        with self.assertRaisesRegex(PublicationRejected, "Protected path"):
            self.broker.validate_changes(self.root, "engineer", self.base)

    def test_new_protected_path_symlink_executable_and_large_file_rejected(self):
        path = self.root / "research/unsafe.md"
        path.symlink_to(self.root / "lean/Challenge.lean")
        with self.assertRaises(PublicationRejected):
            self.broker.validate_changes(self.root, "engineer", self.base)
        path.unlink()
        path.write_text("x" * (256 * 1024 + 1))
        with self.assertRaises(PublicationRejected):
            self.broker.validate_changes(self.root, "engineer", self.base)
        path.write_text("small")
        path.chmod(0o755)
        self.run_git("add", "research/unsafe.md")
        with self.assertRaises(PublicationRejected):
            self.broker.validate_changes(self.root, "engineer", self.base)

    def test_research_evidence_deletion_is_not_automatic(self):
        (self.root / "research/prior.md").unlink()
        with self.assertRaises(PublicationRejected):
            self.broker.validate_changes(self.root, "engineer", self.base)

    def test_protected_staged_change_hidden_by_worktree_restoration_is_rejected(self):
        path = self.root / "lean/Challenge.lean"
        path.write_text("forbidden statement\n")
        self.run_git("add", "lean/Challenge.lean")
        path.write_text("initial\n")
        (self.root / "lean/Colony/Tactic.lean").write_text("allowed change\n")
        with self.assertRaisesRegex(PublicationRejected, "Protected path"):
            self.broker.validate_changes(self.root, "engineer", self.base)

    def test_worker_commit_cannot_hide_a_protected_change_from_publication(self):
        path = self.root / "lean/Challenge.lean"
        path.write_text("forbidden statement\n")
        self.run_git("add", "lean/Challenge.lean")
        self.run_git("commit", "-qm", "Worker unauthorized commit")
        path.write_text("initial\n")
        (self.root / "lean/Colony/Tactic.lean").write_text("allowed change\n")
        with self.assertRaisesRegex(PublicationRejected, "Protected path"):
            self.broker.validate_changes(self.root, "engineer", self.base)
        with self.assertRaisesRegex(PublicationRejected, "Git history"):
            self.broker.commit({"worktree": str(self.root), "base_sha": self.base, "branch": "master"},
                               {"id": "T1", "title": "Example", "role": "engineer"})


if __name__ == "__main__":
    unittest.main()
