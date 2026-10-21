"""Persisted, bounded network backoff helpers."""

import datetime as dt
import time


def retry_delay(attempt, base_seconds=5, max_seconds=900):
    """Deterministic capped exponential backoff (attempts are one-based)."""
    if type(attempt) is not int or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    if type(base_seconds) not in (int, float) or base_seconds <= 0:
        raise ValueError("base_seconds must be positive")
    if type(max_seconds) not in (int, float) or max_seconds < base_seconds:
        raise ValueError("max_seconds must be at least base_seconds")
    return min(float(max_seconds), float(base_seconds) * (2 ** min(attempt - 1, 60)))


def schedule_retry(cycle, update, now=None, base_seconds=5, max_seconds=900):
    attempt = int(cycle.get("network_retry_count", 0)) + 1
    delay = retry_delay(attempt, base_seconds, max_seconds)
    now = time.time() if now is None else float(now)
    return update(cycle, "waiting_network", resume_phase=cycle.get("resume_phase") or cycle["phase"],
                  network_retry_count=attempt, network_retry_delay=delay,
                  next_retry_at=now + delay, last_error="Transient connectivity failure")


def due(cycle, now=None):
    retry_at = cycle.get("next_retry_at")
    return retry_at is None or (time.time() if now is None else now) >= float(retry_at)


def retry_timestamp(cycle):
    value = cycle.get("next_retry_at")
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat() if value else None
