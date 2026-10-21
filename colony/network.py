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
    "error connecting to", "check your internet connection", "no such host",
    "nodename nor servname provided",
    "network is unreachable", "no route to host", "connection reset", "connection refused",
    "connection timed out", "operation timed out", "timed out", "tls handshake timeout",
    "remote end closed", "failed to connect", "502 bad gateway", "503 service unavailable", "504 gateway timeout",
    "http 502", "http 503", "http 504", "bad gateway", "service unavailable",
)
_AUTH_MARKERS = ("authentication failed", "permission denied", "http 401", "http 403",
                 "bad credentials", "resource not accessible by integration", "unauthorized",
                 "model provider authentication requires operator attention")


def classify_connectivity_error(error, remote=True):
    """Return a typed network/auth error for subprocess failures, else None."""
    if isinstance(error, (NetworkUnavailable, AuthenticationFailure)):
        return error
    if not remote:
        return None
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


def classify_model_failure(summary):
    """Recognize explicit provider connectivity errors, never local timeouts."""
    details = str(summary or "").lower()
    if any(marker in details for marker in _AUTH_MARKERS):
        return AuthenticationFailure("Model provider authentication requires operator attention")
    markers = ("model provider connectivity failed", "could not resolve", "connection reset", "connection refused", "failed to connect",
               "tls handshake timeout", "502 bad gateway", "503 service unavailable", "504 gateway timeout")
    if any(marker in details for marker in markers):
        return NetworkUnavailable("Model provider connectivity failed")
    return None


def probe_model_connectivity():
    """Bounded credential-free reachability check, never an inference request.

    Authentication, method and path errors demonstrate a reachable service.
    They do not prove the worker's credentials or subscription are valid.
    """
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
    request = Request("https://chatgpt.com/backend-api/codex/responses", method="HEAD")
    try:
        with urlopen(request, timeout=5):
            return True
    except HTTPError as error:
        if error.code < 500:
            return True
        raise NetworkUnavailable("Model provider reachability probe failed") from error
    except (URLError, OSError) as error:
        raise NetworkUnavailable("Model provider reachability probe failed") from error
