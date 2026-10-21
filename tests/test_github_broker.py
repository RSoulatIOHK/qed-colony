import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from colony.github_broker import GitHubBroker, PublicationRejected, checks_state, validate_public_text
from colony.network import NetworkUnavailable


def passing_pr(sha="a" * 40):
    return {"number": 7, "url": "https://github.com/example/repo/pull/7", "state": "OPEN",
            "headRefOid": sha, "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
                                  for name in ["control-plane", "lean-seed"]]}


def dummy_home_path(home, suffix):
    return "/" + home + "/" + suffix


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
        broker.git = Mock(side_effect=["a" * 40, "a" * 40] * 2)
        broker.find_pr = Mock(return_value=existing)
        broker.gh = Mock()
        result = broker.publish({"worktree": ".", "branch": "codex/cycle", "id": "123"},
                                {"id": "T1", "title": "Example"}, "Measured result")
        self.assertEqual(result, existing)
        broker.gh.assert_not_called()
        self.assertEqual(broker.git.call_count, 2)

    def test_lost_push_response_is_reconciled_from_remote_head_before_retry(self):
        broker = GitHubBroker(".")
        existing = passing_pr()
        broker.git = Mock(side_effect=["a" * 40, "", NetworkUnavailable("push response lost"), "a" * 40])
        broker.find_pr = Mock(return_value=existing)
        result = broker.publish({"worktree": ".", "branch": "codex/cycle", "id": "123"},
                                {"id": "T1", "title": "Example"}, "Candidate")
        self.assertEqual(result, existing)
        self.assertEqual(broker.git.call_count, 4)

    def test_revision_push_uses_exact_recorded_prior_head_lease(self):
        broker = GitHubBroker(".")
        broker.git = Mock(side_effect=["b" * 40, "a" * 40, ""])
        broker.find_pr = Mock(return_value=passing_pr("b" * 40))
        cycle = {"worktree": ".", "branch": "codex/cycle", "id": "123",
                 "publish_previous_head_sha": "a" * 40}
        broker.publish(cycle, {"id": "T1", "title": "Example"}, "Revision")
        self.assertIn("--force-with-lease=refs/heads/codex/cycle:" + "a" * 40,
                      broker.git.call_args_list[2].args)
        self.assertIn("HEAD:refs/heads/codex/cycle", broker.git.call_args_list[2].args)

    def test_new_branch_push_uses_absence_lease(self):
        broker = GitHubBroker(".")
        broker.git = Mock(side_effect=["b" * 40, "", ""])
        broker.find_pr = Mock(return_value=passing_pr("b" * 40))
        broker.publish({"worktree": ".", "branch": "codex/cycle", "id": "123"},
                       {"id": "T1", "title": "Example"}, "Candidate")
        self.assertIn("--force-with-lease=refs/heads/codex/cycle:", broker.git.call_args_list[2].args)

    def test_unrelated_remote_branch_movement_is_not_overwritten(self):
        broker = GitHubBroker(".")
        broker.git = Mock(side_effect=["b" * 40, "c" * 40])
        broker.find_pr = Mock()
        with self.assertRaises(PublicationRejected):
            broker.publish({"worktree": ".", "branch": "codex/cycle", "id": "123",
                            "publish_previous_head_sha": "a" * 40},
                           {"id": "T1", "title": "Example"}, "Revision")
        self.assertEqual(broker.git.call_count, 2)
        broker.find_pr.assert_not_called()

    def test_lost_revision_push_response_reconciles_without_second_push(self):
        broker = GitHubBroker(".")
        broker.git = Mock(side_effect=["b" * 40, "a" * 40, NetworkUnavailable("lost"), "b" * 40,
                                      "b" * 40, "b" * 40])
        broker.find_pr = Mock(return_value=passing_pr("b" * 40))
        cycle = {"worktree": ".", "branch": "codex/cycle", "id": "123",
                 "publish_previous_head_sha": "a" * 40}
        task = {"id": "T1", "title": "Example"}
        broker.publish(cycle, task, "Revision")
        broker.publish(cycle, task, "Revision")
        pushes = [c for c in broker.git.call_args_list if c.args[1] == "push"]
        self.assertEqual(len(pushes), 1)

    def test_remote_pr_create_then_lost_response_reuses_discovered_pr(self):
        broker = GitHubBroker(".")
        existing = passing_pr()
        broker.git = Mock(side_effect=["a" * 40, "a" * 40] * 2)
        broker.find_pr = Mock(side_effect=[None, existing, existing])
        calls = {"create": 0}

        def gh(*args):
            if args[:2] == ("pr", "create"):
                calls["create"] += 1
                raise NetworkUnavailable("response lost after creation")

        broker.gh = Mock(side_effect=gh)
        cycle = {"worktree": ".", "branch": "codex/cycle", "id": "123"}
        task = {"id": "S1", "title": "Recover network errors", "role": "sre"}
        with self.assertRaises(NetworkUnavailable):
            broker.publish(cycle, task, "Candidate")
        # Simulate the external PR appearing before the next publish attempt.
        broker.find_pr = Mock(side_effect=[existing, existing])
        self.assertEqual(broker.publish(cycle, task, "Candidate"), existing)
        self.assertEqual(calls["create"], 1)

    def test_sre_publication_is_explicitly_a_separate_governance_pr(self):
        broker = GitHubBroker(".")
        broker.git = Mock(side_effect=["a" * 40, "a" * 40])
        broker.find_pr = Mock(side_effect=[None, passing_pr()])
        published = {}

        def create(*args):
            published["title"] = args[args.index("--title") + 1]
            published["body"] = Path(args[args.index("--body-file") + 1]).read_text()

        broker.gh = Mock(side_effect=create)
        broker.publish({"worktree": ".", "branch": "codex/sre", "id": "s1"},
                       {"id": "S1", "title": "Recover network errors", "role": "sre"}, "A bounded recovery candidate")
        self.assertEqual(published["title"], "Governance: S1: Recover network errors")
        self.assertIn("separate governance PR", published["body"])
        self.assertIn("awaits controller integration", published["body"])
        self.assertIn("never automatically merges or deploys", published["body"])

    def test_review_comment_is_idempotent_and_honestly_labelled(self):
        broker = GitHubBroker(".")
        broker.gh = Mock(return_value=json.dumps([[{"body": "Unrelated old comment"}], [{"body": "<!-- colony-review:c1:abc -->"}]]))
        broker.comment_review(7, {"verdict": "approve", "summary": "Correct", "findings": []}, "abc", "c1")
        self.assertEqual(broker.gh.call_count, 1)

    def test_public_text_rejects_secrets_and_machine_paths(self):
        for value in [dummy_home_path("Users", "someone/project/file"),
                      "ghp_" + "a" * 30, "-----BEGIN " + "PRIVATE KEY-----"]:
            with self.assertRaises(PublicationRejected):
                validate_public_text(value)
        self.assertEqual(validate_public_text("lean/Colony/Tactic.lean"), "lean/Colony/Tactic.lean")

    def test_failure_details_redacts_runner_paths_and_keeps_actionable_filename(self):
        broker = GitHubBroker(".", {"repository": "example/qed-colony"})
        broker._bounded_log = Mock(return_value=(
            'File "' + dummy_home_path("home", "runner/work/qed-colony/qed-colony/scripts/evaluate_lean.py") + '", line 42\n'
            + dummy_home_path("home", "runner/.elan/toolchains/lean/bin/lean") + ': failure\n'
            + dummy_home_path("Users", "runner/work/qed-colony/qed-colony/lean/Colony/Tactic.lean") + ':7: error'))
        pr = {"statusCheckRollup": [{"name": "lean-seed", "conclusion": "FAILURE",
                                   "detailsUrl": "https://github.com/example/qed-colony/actions/runs/123/job/456"}]}
        details = broker.failure_details(pr)
        self.assertIn('File "<checkout>/scripts/evaluate_lean.py", line 42', details)
        self.assertIn("<checkout>/lean/Colony/Tactic.lean:7: error", details)
        self.assertIn("<runner-home>/.elan/toolchains/lean/bin/lean", details)
        self.assertNotIn("/home/", details)
        self.assertNotIn("/Users/", details)
        broker._bounded_log.assert_called_once_with("123")

    def test_failure_details_still_rejects_credentials_after_path_redaction(self):
        broker = GitHubBroker(".", {"repository": "example/qed-colony"})
        broker._bounded_log = Mock(return_value=dummy_home_path("home", "runner/work/qed-colony/qed-colony/file")
                                   + " ghp_" + "a" * 30)
        pr = {"statusCheckRollup": [{"name": "lean-seed", "conclusion": "FAILURE",
                                   "detailsUrl": "https://github.com/example/qed-colony/actions/runs/123/job/456"}]}
        with self.assertRaises(PublicationRejected):
            broker.failure_details(pr)


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

    def test_sre_can_publish_narrow_controller_recovery_code_and_tests(self):
        for name in ["colony/network_recovery.py", "colony/pipeline.py", "tests/test_network_recovery.py",
                     "docs/network-recovery.md", "research/recovery.md"]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Scoped recovery proposal\n")
        paths = self.broker.validate_changes(self.root, "sre", self.base)
        self.assertIn("colony/network_recovery.py", paths)
        self.assertIn("tests/test_network_recovery.py", paths)
        with self.assertRaisesRegex(PublicationRejected, "Protected path"):
            self.broker.validate_changes(self.root, "engineer", self.base)

    def test_sre_cannot_publish_authority_configuration_evaluator_or_lean_changes(self):
        for name in ["colony/service.py", "colony/__main__.py", "colony/model_policy.py", "colony.json", "AGENTS.md",
                     ".github/workflows/ci.yml", "scripts/evaluate_lean.py", "lean/Challenge.lean",
                     "benchmarks/seed-v1.json", "lean/Colony/Tactic.lean"]:
            with self.subTest(path=name):
                path = self.root / name
                existed = path.exists()
                original = path.read_text() if existed else None
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Forbidden scoped modification\n")
                try:
                    with self.assertRaises(PublicationRejected):
                        self.broker.validate_changes(self.root, "sre", self.base)
                finally:
                    if existed:
                        path.write_text(original)
                    else:
                        path.unlink()


if __name__ == "__main__":
    unittest.main()
