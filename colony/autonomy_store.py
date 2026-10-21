"""Durable controller state and conservative, transactional model budgets.

This is local operational state, not a security boundary against its file owner.
An unfinished attempt retains its entire reservation after a controller crash.
"""

import contextlib
import datetime as dt
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid
from zoneinfo import ZoneInfo

from .store import timestamp


TERMINAL_PHASES = frozenset({"done", "failed", "blocked", "needs_review"})
DEFAULT_POLICY = {
    "max_daily_seconds": 3600,
    "max_daily_attempts": 12,
    "timezone": "Europe/Paris",
}


class BudgetExceeded(RuntimeError):
    """Launching this model attempt would exceed the configured daily cap."""


class CapacityUnavailable(RuntimeError):
    """No model lane is available; no attempt or runtime is charged."""


class DuplicateAttempt(RuntimeError):
    """A stage already has a durable attempt, including an interrupted attempt."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _limits(policy):
    policy = dict(DEFAULT_POLICY, **(policy or {}))
    seconds = policy["max_daily_seconds"]
    attempts = policy["max_daily_attempts"]
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
        raise ValueError("max_daily_seconds must be a finite nonnegative number")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
        raise ValueError("max_daily_attempts must be a nonnegative integer")
    zone = ZoneInfo(policy["timezone"])
    return float(seconds), attempts, zone


def _concurrency_limit(policy):
    limit = (policy or {}).get("max_concurrency", 1)
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("max_concurrency must be an integer between 1 and 16")
    return limit


class AutonomyStore:
    def __init__(self, db_path, clock=None):
        self.path = Path(db_path)
        self.clock = clock or time.time

    @contextlib.contextmanager
    def _connection(self, write=False):
        conn = sqlite3.connect(str(self.path), timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if write:
                conn.commit()
        except BaseException:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS autonomy_cycles (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS autonomy_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id TEXT NOT NULL REFERENCES autonomy_cycles(id),
                    stage TEXT NOT NULL,
                    local_date TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    timeout_seconds REAL NOT NULL,
                    charged_seconds REAL NOT NULL,
                    elapsed_seconds REAL,
                    status TEXT NOT NULL,
                    usage TEXT NOT NULL DEFAULT '{}',
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    UNIQUE(cycle_id, stage)
                );
                CREATE INDEX IF NOT EXISTS autonomy_attempts_date ON autonomy_attempts(local_date);
                CREATE TABLE IF NOT EXISTS autonomy_service (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    status TEXT NOT NULL,
                    pid INTEGER,
                    active_cycle TEXT,
                    message TEXT NOT NULL DEFAULT '',
                    heartbeat REAL NOT NULL
                );
            """)
        return self

    @staticmethod
    def _cycle(row):
        if row is None:
            return None
        result = json.loads(row["data"])
        # Fixed metadata cannot be overwritten by the opaque pipeline context.
        result.update({key: row[key] for key in ("id", "task_id", "role", "phase")})
        result.update({key: timestamp(row[key]) for key in ("created_at", "updated_at")})
        return result

    def create_cycle(self, task_id, role):
        if not all(isinstance(item, str) and item.strip() for item in (task_id, role)):
            raise ValueError("task_id and role must be nonempty strings")
        now = self.clock()
        with self._connection(write=True) as conn:
            conn.execute("""INSERT OR IGNORE INTO autonomy_cycles(id,task_id,role,phase,created_at,updated_at)
                VALUES(?,?,?,'queued',?,?)""", (uuid.uuid4().hex, task_id, role, now, now))
            return self._cycle(conn.execute("SELECT * FROM autonomy_cycles WHERE task_id=?", (task_id,)).fetchone())

    def get_cycle(self, cycle_id):
        with self._connection() as conn:
            return self._cycle(conn.execute("SELECT * FROM autonomy_cycles WHERE id=?", (cycle_id,)).fetchone())

    def next_cycle(self):
        with self._connection() as conn:
            row = conn.execute("""SELECT * FROM autonomy_cycles
                WHERE phase NOT IN ('done','failed','blocked','needs_review')
                ORDER BY created_at,id LIMIT 1""").fetchone()
            return self._cycle(row)

    def list_cycles(self):
        with self._connection() as conn:
            return [self._cycle(row) for row in conn.execute("SELECT * FROM autonomy_cycles ORDER BY created_at,id")]

    def update_cycle(self, cycle_id, phase=None, **data):
        if phase is not None and (not isinstance(phase, str) or not phase.strip()):
            raise ValueError("phase must be a nonempty string")
        if set(data) & {"id", "task_id", "role", "created_at", "updated_at"}:
            raise ValueError("Fixed cycle metadata cannot be changed")
        with self._connection(write=True) as conn:
            row = conn.execute("SELECT * FROM autonomy_cycles WHERE id=?", (cycle_id,)).fetchone()
            if row is None:
                raise KeyError(cycle_id)
            context = json.loads(row["data"])
            context.update(data)
            conn.execute("UPDATE autonomy_cycles SET phase=?,data=?,updated_at=? WHERE id=?",
                         (row["phase"] if phase is None else phase, _json(context), self.clock(), cycle_id))
            return self._cycle(conn.execute("SELECT * FROM autonomy_cycles WHERE id=?", (cycle_id,)).fetchone())

    def _budget(self, conn, policy, now):
        seconds, attempts, zone = _limits(policy)
        limit = _concurrency_limit(policy)
        local_date = dt.datetime.fromtimestamp(now, zone).date().isoformat()
        row = conn.execute("""SELECT COUNT(*) AS attempts,COALESCE(SUM(charged_seconds),0) AS seconds,
            COALESCE(SUM(CASE WHEN status='running' THEN charged_seconds ELSE 0 END),0) AS reserved
            FROM autonomy_attempts WHERE local_date=?""", (local_date,)).fetchone()
        remaining = max(0.0, seconds - row["seconds"])
        remaining_attempts = max(0, attempts - row["attempts"])
        tomorrow = dt.datetime.combine(dt.datetime.fromtimestamp(now, zone).date() + dt.timedelta(days=1), dt.time(), zone)
        # Capacity spans budget days: a call started before midnight still
        # occupies its lane. Uncertain process slots never expire by time.
        active = conn.execute("SELECT cycle_id FROM autonomy_attempts WHERE status='running' ORDER BY id").fetchall()
        worker_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='worker_runs'").fetchone()
        uncertain = conn.execute("SELECT COUNT(*) FROM worker_runs WHERE status='uncertain'").fetchone()[0] if worker_table else 0
        return {"local_date": local_date, "timezone": str(zone), "max_daily_seconds": seconds,
                "max_daily_attempts": attempts, "used_seconds": row["seconds"],
                "reserved_seconds": row["reserved"], "remaining_seconds": remaining,
                "attempts": row["attempts"], "remaining_attempts": remaining_attempts,
                "exhausted": remaining <= 0 or remaining_attempts <= 0,
                "active_attempts": len(active), "active_cycle_ids": list(dict.fromkeys(item["cycle_id"] for item in active)),
                "uncertain_workers": uncertain, "concurrency_limit": limit,
                "resets_at": timestamp(tomorrow.timestamp())}

    def get_budget(self, policy=None):
        with self._connection() as conn:
            return self._budget(conn, policy, self.clock())

    def reserve_attempt(self, cycle_id, stage, timeout_seconds, policy=None):
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        if not isinstance(stage, str) or not stage.strip():
            raise ValueError("stage must be a nonempty string")
        now = self.clock()
        with self._connection(write=True) as conn:
            if conn.execute("SELECT 1 FROM autonomy_cycles WHERE id=?", (cycle_id,)).fetchone() is None:
                raise KeyError(cycle_id)
            previous = conn.execute("SELECT status FROM autonomy_attempts WHERE cycle_id=? AND stage=?", (cycle_id, stage)).fetchone()
            if previous and previous["status"] == "running":
                raise CapacityUnavailable("This cycle stage is already running")
            if previous:
                raise DuplicateAttempt("Stage already attempted: %s" % stage)
            budget = self._budget(conn, policy, now)
            if budget["remaining_attempts"] <= 0 or budget["remaining_seconds"] < timeout_seconds:
                raise BudgetExceeded("Daily model budget cannot reserve %s seconds; resets %s" % (timeout_seconds, budget["resets_at"]))
            if (cycle_id in budget["active_cycle_ids"] or
                    budget["active_attempts"] + budget["uncertain_workers"] >= budget["concurrency_limit"]):
                raise CapacityUnavailable("Model concurrency allocation is occupied")
            cursor = conn.execute("""INSERT INTO autonomy_attempts
                (cycle_id,stage,local_date,timezone,timeout_seconds,charged_seconds,status,started_at)
                VALUES(?,?,?,?,?,?,'running',?)""",
                (cycle_id, stage, budget["local_date"], budget["timezone"], timeout_seconds, timeout_seconds, now))
            return cursor.lastrowid

    def finish_attempt(self, attempt_id, elapsed_seconds, usage=None, status="completed"):
        if status not in {"completed", "failed", "interrupted"}:
            raise ValueError("Attempt status must be completed, failed, or interrupted")
        if isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, (int, float)) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be a finite nonnegative number")
        if usage is not None and not isinstance(usage, dict):
            raise ValueError("usage must be an object")
        with self._connection(write=True) as conn:
            row = conn.execute("SELECT * FROM autonomy_attempts WHERE id=?", (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(attempt_id)
            # Never permit a second completion to release an interrupted charge.
            if row["status"] != "running":
                return self._attempt(row)
            charged = row["timeout_seconds"] if status == "interrupted" else max(elapsed_seconds, 0.0)
            conn.execute("""UPDATE autonomy_attempts SET elapsed_seconds=?,charged_seconds=?,usage=?,status=?,finished_at=?
                WHERE id=?""", (elapsed_seconds, charged, _json(usage or {}), status, self.clock(), attempt_id))
            return self._attempt(conn.execute("SELECT * FROM autonomy_attempts WHERE id=?", (attempt_id,)).fetchone())

    @staticmethod
    def _attempt(row):
        result = dict(row)
        result["usage"] = json.loads(result["usage"])
        for key in ("started_at", "finished_at"):
            if result[key] is not None:
                result[key] = timestamp(result[key])
        return result

    def list_attempts(self, cycle_id=None):
        with self._connection() as conn:
            if cycle_id is None:
                rows = conn.execute("SELECT * FROM autonomy_attempts ORDER BY id")
            else:
                rows = conn.execute("SELECT * FROM autonomy_attempts WHERE cycle_id=? ORDER BY id", (cycle_id,))
            return [self._attempt(row) for row in rows]

    def reconcile_interrupted(self):
        """Call only while owning the controller lock, before launching workers."""
        now = self.clock()
        with self._connection(write=True) as conn:
            rows = conn.execute("SELECT * FROM autonomy_attempts WHERE status='running' ORDER BY id").fetchall()
            for row in rows:
                conn.execute("UPDATE autonomy_attempts SET status='interrupted',finished_at=? WHERE id=?", (now, row["id"]))
                cycle = conn.execute("SELECT * FROM autonomy_cycles WHERE id=?", (row["cycle_id"],)).fetchone()
                context = json.loads(cycle["data"])
                context.update({"interrupted_stage": row["stage"], "last_error": "Controller stopped during a model attempt; automatic repetition is disabled."})
                conn.execute("UPDATE autonomy_cycles SET phase='needs_review',data=?,updated_at=? WHERE id=?",
                             (_json(context), now, row["cycle_id"]))
            return [self._attempt(conn.execute("SELECT * FROM autonomy_attempts WHERE id=?", (row["id"],)).fetchone()) for row in rows]

    def set_service(self, status, pid, active_cycle=None, message=""):
        if not isinstance(status, str) or not status:
            raise ValueError("Service status must be nonempty")
        with self._connection(write=True) as conn:
            conn.execute("""INSERT INTO autonomy_service(singleton,status,pid,active_cycle,message,heartbeat)
                VALUES(1,?,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET
                status=excluded.status,pid=excluded.pid,active_cycle=excluded.active_cycle,
                message=excluded.message,heartbeat=excluded.heartbeat""", (status, pid, active_cycle, str(message), self.clock()))
        return self.service_snapshot()

    def service_snapshot(self, policy=None):
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM autonomy_service WHERE singleton=1").fetchone()
            if row is None:
                service = {"status": "stopped", "pid": None, "active_cycle": None, "message": "Supervisor has not started",
                           "heartbeat": None, "heartbeat_age_seconds": None, "stale": True}
            else:
                service = {key: row[key] for key in ("status", "pid", "active_cycle", "message")}
                service.update({"heartbeat": timestamp(row["heartbeat"]), "heartbeat_age_seconds": max(0, self.clock() - row["heartbeat"]),
                                "stale": self.clock() - row["heartbeat"] > 120})
            if policy is not None:
                service["budget"] = self._budget(conn, policy, self.clock())
            return service

    def heartbeat_service(self, pid):
        """Refresh a live controller without overwriting its current phase."""
        with self._connection(write=True) as conn:
            conn.execute("UPDATE autonomy_service SET heartbeat=? WHERE singleton=1 AND pid=?",
                         (self.clock(), pid))
