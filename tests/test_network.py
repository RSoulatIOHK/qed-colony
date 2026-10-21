import subprocess
import unittest

from colony.network import AuthenticationFailure, NetworkUnavailable, classify_connectivity_error


class NetworkClassificationTests(unittest.TestCase):
    def test_transient_remote_errors_are_network_waits(self):
        error = subprocess.CalledProcessError(128, ["git"], stderr="fatal: Could not resolve host")
        self.assertIsInstance(classify_connectivity_error(error), NetworkUnavailable)

    def test_authentication_errors_remain_attention_failures(self):
        error = subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 401: Bad credentials")
        self.assertIsInstance(classify_connectivity_error(error), AuthenticationFailure)

    def test_candidate_errors_are_not_reclassified(self):
        error = subprocess.CalledProcessError(1, ["git"], stderr="bad object name")
        self.assertIsNone(classify_connectivity_error(error))

    def test_local_permission_failure_is_not_called_a_network_outage(self):
        self.assertIsNone(classify_connectivity_error(PermissionError("operation not permitted")))
