import subprocess
import unittest
from unittest.mock import Mock, patch

from colony.github_broker import GitHubBroker
from colony.network import AuthenticationFailure, NetworkUnavailable, classify_connectivity_error, probe_model_connectivity


class NetworkClassificationTests(unittest.TestCase):
    def test_transient_remote_errors_are_network_waits(self):
        error = subprocess.CalledProcessError(128, ["git"], stderr="fatal: Could not resolve host")
        self.assertIsInstance(classify_connectivity_error(error), NetworkUnavailable)

    def test_actual_gh_and_go_dns_diagnostics_become_network_waits(self):
        for diagnostic in [
                "error connecting to api.github.com\ncheck your internet connection or https://githubstatus.com",
                "dial tcp: lookup api.github.com: no such host",
                "[Errno 8] nodename nor servname provided, or not known"]:
            with self.subTest(diagnostic=diagnostic):
                error = subprocess.CalledProcessError(1, ["gh"], stderr=diagnostic)
                self.assertIsInstance(classify_connectivity_error(error), NetworkUnavailable)
                self.assertIsNone(classify_connectivity_error(error, remote=False))

    def test_authentication_errors_remain_attention_failures(self):
        error = subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 401: Bad credentials")
        self.assertIsInstance(classify_connectivity_error(error), AuthenticationFailure)

    def test_candidate_errors_are_not_reclassified(self):
        error = subprocess.CalledProcessError(1, ["git"], stderr="bad object name")
        self.assertIsNone(classify_connectivity_error(error))

    def test_local_permission_failure_is_not_called_a_network_outage(self):
        self.assertIsNone(classify_connectivity_error(PermissionError("operation not permitted")))

    def test_local_git_timeout_is_not_called_a_network_outage(self):
        broker = GitHubBroker(".", runner=Mock(side_effect=subprocess.TimeoutExpired("git commit", 120)))
        with self.assertRaises(subprocess.TimeoutExpired):
            broker.git(".", "commit", "-m", "local")

    def test_remote_git_timeout_is_retryable(self):
        broker = GitHubBroker(".", runner=Mock(side_effect=subprocess.TimeoutExpired("git push", 120)))
        with self.assertRaises(NetworkUnavailable):
            broker.git(".", "push", "origin", "branch")


class ProviderProbeTests(unittest.TestCase):
    def test_probe_is_head_only_and_requires_no_credentials(self):
        from urllib.error import HTTPError
        with patch("urllib.request.urlopen", side_effect=HTTPError("https://example.invalid", 401, "auth", {}, None)) as open_url:
            self.assertTrue(probe_model_connectivity())
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_method(), "HEAD")
        self.assertIsNone(request.data)
        self.assertFalse(request.has_header("Authorization"))
        self.assertEqual(open_url.call_args.kwargs["timeout"], 5)

    def test_probe_failure_is_network_wait_and_does_not_make_model_call(self):
        from urllib.error import HTTPError, URLError
        for error in [URLError("offline"), HTTPError("https://example.invalid", 503, "unavailable", {}, None)]:
            with self.subTest(error=type(error).__name__), patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(NetworkUnavailable):
                    probe_model_connectivity()
