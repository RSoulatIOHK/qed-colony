"""Classification of transient connectivity failures from bounded controller calls."""

import subprocess
import errno
import socket


class NetworkUnavailable(ConnectionError):
    """A retryable connectivity failure; the associated operation may have succeeded remotely."""


class AuthenticationFailure(RuntimeError):
    """Credentials or authorization need operator attention."""


_NETWORK_MARKERS = (
    "could not resolve", "temporary failure in name resolution", "name or service not known",
    "network is unreachable", "no route to host", "connection reset", "connection refused",
    "connection timed out", "operation timed out", "timed out", "tls handshake timeout",
    "remote end closed", "could not read from remote repository", "failed to connect",
    "unable to access", "502 bad gateway", "503 service unavailable", "504 gateway timeout",
    "http 502", "http 503", "http 504", "bad gateway", "service unavailable",
)
_AUTH_MARKERS = ("authentication failed", "permission denied", "http 401", "http 403",
                 "bad credentials", "resource not accessible by integration", "unauthorized")


def classify_connectivity_error(error):
    """Return a typed network/auth error for subprocess failures, else None."""
    if isinstance(error, (NetworkUnavailable, AuthenticationFailure)):
        return error
    if isinstance(error, OSError) and not isinstance(error, (socket.gaierror, TimeoutError)):
        if getattr(error, "errno", None) not in {
            errno.ECONNRESET, errno.ECONNREFUSED, errno.ECONNABORTED,
            errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ETIMEDOUT,
            errno.EPIPE,
        }:
            return None
    if not isinstance(error, (subprocess.SubprocessError, OSError, TimeoutError)):
        return None
    details = " ".join(str(part) for part in (
        getattr(error, "stderr", ""), getattr(error, "stdout", ""), error
    ) if part).lower()
    if any(marker in details for marker in _AUTH_MARKERS):
        return AuthenticationFailure("Remote authentication or authorization failed")
    if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)) or any(marker in details for marker in _NETWORK_MARKERS):
        return NetworkUnavailable("Transient connectivity failure")
    return None
