"""Small SQLite task store. All claims and task mutations are transactional."""

import contextlib
import datetime as dt
import json
from pathlib import Path
import sqlite3
import time


STATUSES = {"ready", "running", "review", "blocked", "done", "failed"}
TRANSITIONS = {
    "ready": {"blocked", "failed"},
    "running": {"ready", "review", "blocked", "done", "failed"},
    "review": {"ready", "done", "blocked", "failed"},
    "blocked": {"ready", "failed"},
    "failed": {"ready", "blocked"},
    "done": set(),
}


def timestamp(value=None):
    """An ISO 8601 UTC timestamp, suitable for the public event stream."""
    value = time.time() if value is None else value
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class Store:
    def __init__(self, path):
        self.path = Path(path)

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
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('ready','running','review','blocked','done','failed')),
                    priority INTEGER NOT NULL DEFAULT 0,
                    depends_on TEXT NOT NULL DEFAULT '[]',
                    acceptance TEXT NOT NULL DEFAULT '[]',
                    description TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    branch TEXT,
                    pr_url TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    lease_owner TEXT,
                    lease_until REAL,
                    block_reason TEXT
                );
                CREATE INDEX IF NOT EXISTS tasks_queue ON tasks(status, priority DESC, created_at);
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'idle',
                    task_id TEXT REFERENCES tasks(id),
                    last_seen REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at REAL NOT NULL,
                    kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    task_id TEXT,
                    message TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TRIGGER IF NOT EXISTS events_no_update
                    BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete
                    BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
                CREATE TABLE IF NOT EXISTS benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at REAL NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at REAL NOT NULL,
                    data TEXT NOT NULL
                );
            """)
        return self

    @staticmethod
    def _event(conn, kind, actor, message, task_id=None, data=None, now=None):
        cursor = conn.execute(
            "INSERT INTO events(at,kind,actor,task_id,message,data) VALUES(?,?,?,?,?,?)",
            (time.time() if now is None else now, kind, actor, task_id, message, _json({} if data is None else data)),
        )
        return cursor.lastrowid

    @staticmethod
    def _task(row):
        if row is None:
            return None
        result = dict(row)
        result.pop("block_reason", None)
        result["depends_on"] = json.loads(result["depends_on"])
        result["acceptance"] = json.loads(result["acceptance"])
        for key in ("created_at", "updated_at", "lease_until"):
            if result[key] is not None:
                result[key] = timestamp(result[key])
        return result

    @staticmethod
    def _agent(row):
        if row is None:
            return None
        result = dict(row)
        result["last_seen"] = timestamp(result["last_seen"])
        return result

    def _refresh_dependencies(self, conn, now):
        statuses = {row["id"]: row["status"] for row in conn.execute("SELECT id,status FROM tasks")}
        for row in conn.execute("SELECT * FROM tasks WHERE status IN ('ready','blocked')").fetchall():
            unmet = [item for item in json.loads(row["depends_on"]) if statuses.get(item) != "done"]
            if row["status"] == "ready" and unmet:
                conn.execute("UPDATE tasks SET status='blocked',block_reason='dependencies',updated_at=? WHERE id=?", (now, row["id"]))
                self._event(conn, "task.blocked", "scheduler", "Waiting for dependencies", row["id"], {"depends_on": unmet}, now)
            elif row["status"] == "blocked" and row["block_reason"] == "dependencies" and not unmet:
                conn.execute("UPDATE tasks SET status='ready',block_reason=NULL,updated_at=? WHERE id=?", (now, row["id"]))
                self._event(conn, "task.ready", "scheduler", "All dependencies completed", row["id"], now=now)

    def seed(self, tasks):
        """Insert missing task IDs. Existing tasks, including their status, are untouched."""
        prepared = []
        for task in tasks:
            item = dict(task)
            for field in ("id", "title", "role"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise ValueError("Task %s must be a nonempty string" % field)
            status = item.get("status", "ready")
            if status not in STATUSES or status == "running":
                raise ValueError("Seed status must be ready, review, blocked, done, or failed")
            dependencies = item.get("depends_on", [])
            if not isinstance(dependencies, list) or any(not isinstance(dep, str) or not dep for dep in dependencies):
                raise ValueError("depends_on must be a list of task IDs")
            if item["id"] in dependencies:
                raise ValueError("A task cannot depend on itself")
            item["status"] = status
            item["depends_on"] = dependencies
            prepared.append(item)
        now = time.time()
        inserted = 0
        with self._connection(write=True) as conn:
            for item in prepared:
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO tasks(id,title,role,status,priority,depends_on,acceptance,description,created_at,updated_at,block_reason)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """, (item["id"], item["title"], item["role"], item["status"], int(item.get("priority", 0)),
                      _json(item["depends_on"]), _json(item.get("acceptance", [])), item.get("description", ""),
                      now, now, "explicit" if item["status"] == "blocked" else None))
                if cursor.rowcount:
                    inserted += 1
                    self._event(conn, "task.created", "seed", item["title"], item["id"], {"role": item["role"]}, now)
            self._refresh_dependencies(conn, now)
        return inserted

    def register_agent(self, agent_id, name, role):
        if not all(isinstance(value, str) and value.strip() for value in (agent_id, name, role)):
            raise ValueError("Agent id, name, and role must be nonempty strings")
        now = time.time()
        with self._connection(write=True) as conn:
            existed = conn.execute("SELECT 1 FROM agents WHERE id=?", (agent_id,)).fetchone()
            conn.execute("""INSERT INTO agents(id,name,role,last_seen) VALUES(?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,role=excluded.role,last_seen=excluded.last_seen""", (agent_id, name, role, now))
            if not existed:
                self._event(conn, "agent.registered", agent_id, "%s joined as %s" % (name, role), now=now)
            return self._agent(conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone())

    def _recover_expired(self, conn, now):
        rows = conn.execute("SELECT * FROM tasks WHERE status='running' AND lease_until<=?", (now,)).fetchall()
        for row in rows:
            conn.execute("UPDATE tasks SET status='ready',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE id=?", (now, row["id"]))
            conn.execute("UPDATE agents SET status='idle',task_id=NULL WHERE id=? AND task_id=?", (row["lease_owner"], row["id"]))
            self._event(conn, "lease.expired", "scheduler", "Expired lease recovered; task is available again", row["id"], {"previous_owner": row["lease_owner"]}, now)
        self._refresh_dependencies(conn, now)
        return len(rows)

    def recover_expired(self):
        with self._connection(write=True) as conn:
            return self._recover_expired(conn, time.time())

    def claim(self, agent_id, role=None, lease_seconds=300, task_id=None):
        """Atomically claim the highest priority ready task. One active task per agent."""
        if not isinstance(lease_seconds, (int, float)) or not 0 < lease_seconds <= 86400:
            raise ValueError("lease_seconds must be between 0 and 86400")
        now = time.time()
        with self._connection(write=True) as conn:
            self._recover_expired(conn, now)
            agent = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
            if agent is None:
                raise KeyError("Register agent before claiming a task: %s" % agent_id)
            active = conn.execute("SELECT * FROM tasks WHERE status='running' AND lease_owner=?", (agent_id,)).fetchone()
            if active:
                return None
            query = "SELECT * FROM tasks WHERE status='ready'"
            args = []
            if role is not None:
                query += " AND role=?"
                args.append(role)
            if task_id is not None:
                query += " AND id=?"
                args.append(task_id)
            query += " ORDER BY priority DESC,created_at,id LIMIT 1"
            row = conn.execute(query, args).fetchone()
            conn.execute("UPDATE agents SET last_seen=? WHERE id=?", (now, agent_id))
            if row is None:
                return None
            conn.execute("UPDATE tasks SET status='running',lease_owner=?,lease_until=?,updated_at=?,block_reason=NULL WHERE id=?", (agent_id, now + lease_seconds, now, row["id"]))
            conn.execute("UPDATE agents SET status='working',task_id=?,last_seen=? WHERE id=?", (row["id"], now, agent_id))
            self._event(conn, "task.claimed", agent_id, "Claimed %s" % row["title"], row["id"], {"lease_seconds": lease_seconds}, now)
            return self._task(conn.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone())

    @staticmethod
    def _require_owner(row, agent_id, now):
        if row["status"] != "running" or row["lease_owner"] != agent_id or row["lease_until"] is None or row["lease_until"] <= now:
            raise PermissionError("Task requires its current, unexpired lease owner")

    def heartbeat(self, task_id, agent_id, lease_seconds=300):
        if not isinstance(lease_seconds, (int, float)) or not 0 < lease_seconds <= 86400:
            raise ValueError("lease_seconds must be between 0 and 86400")
        now = time.time()
        with self._connection(write=True) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            self._require_owner(row, agent_id, now)
            conn.execute("UPDATE tasks SET lease_until=?,updated_at=? WHERE id=?", (now + lease_seconds, now, task_id))
            conn.execute("UPDATE agents SET last_seen=? WHERE id=?", (now, agent_id))
            return self._task(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def transition(self, task_id, status, actor, summary="", branch=None, pr_url=None):
        if status not in STATUSES:
            raise ValueError("Unknown task status: %s" % status)
        if pr_url is not None and not pr_url.startswith("https://"):
            raise ValueError("pr_url must be an actual HTTPS pull request URL")
        now = time.time()
        with self._connection(write=True) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["status"] == "running":
                self._require_owner(row, actor, now)
            if status == row["status"]:
                return self._task(row)
            if status not in TRANSITIONS[row["status"]]:
                raise ValueError("Invalid transition: %s -> %s" % (row["status"], status))
            conn.execute("""UPDATE tasks SET status=?,summary=?,branch=COALESCE(?,branch),pr_url=COALESCE(?,pr_url),
                lease_owner=NULL,lease_until=NULL,block_reason=?,updated_at=? WHERE id=?""",
                (status, summary, branch, pr_url, "explicit" if status == "blocked" else None, now, task_id))
            if row["lease_owner"]:
                conn.execute("UPDATE agents SET status='idle',task_id=NULL,last_seen=? WHERE id=? AND task_id=?", (now, row["lease_owner"], task_id))
            self._event(conn, "task.%s" % status, actor, summary or "%s → %s" % (row["status"], status), task_id,
                        {"from": row["status"], "to": status, "branch": branch, "pr_url": pr_url}, now)
            self._refresh_dependencies(conn, now)
            return self._task(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def get_task(self, task_id):
        with self._connection() as conn:
            return self._task(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

    def complete_recovery(self, source_task_id, replacement_task_id, expected_description,
                          expected_acceptance, replacement_pr_url, actor="controller"):
        """Resolve the original only after controller-verified replacement integration.

        Remote exact-head review, CI and closure are the pipeline's responsibility.
        This transaction preserves acceptance and releases dependencies exactly once.
        """
        if source_task_id == replacement_task_id or not isinstance(replacement_pr_url, str) or not replacement_pr_url.startswith("https://"):
            raise ValueError("Recovery requires a distinct replacement and HTTPS PR")
        now = time.time()
        with self._connection(write=True) as conn:
            source = self._task(conn.execute("SELECT * FROM tasks WHERE id=?", (source_task_id,)).fetchone())
            replacement = self._task(conn.execute("SELECT * FROM tasks WHERE id=?", (replacement_task_id,)).fetchone())
            if source is None or replacement is None:
                raise ValueError("Recovery source or replacement is missing")
            if (source["description"] != expected_description or source["acceptance"] != expected_acceptance
                    or replacement["acceptance"] != expected_acceptance
                    or not replacement["description"].startswith(expected_description)
                    or source["role"] != replacement["role"]
                    or replacement["status"] != "done" or replacement["pr_url"] != replacement_pr_url):
                raise ValueError("Recovery acceptance, role, or integrated replacement differs")
            summary = "Original acceptance satisfied by reviewed replacement " + replacement_pr_url
            if source["status"] == "done":
                if source["summary"] != summary:
                    raise ValueError("Source was completed by another action")
                return source
            if source["status"] not in {"blocked", "failed", "review"}:
                raise ValueError("Recovery source must be parked, not executing")
            conn.execute("UPDATE tasks SET status='done',summary=?,lease_owner=NULL,lease_until=NULL,block_reason=NULL,updated_at=? WHERE id=?",
                         (summary, now, source_task_id))
            self._event(conn, "task.recovery_completed", actor, summary, source_task_id,
                        {"replacement_task_id": replacement_task_id, "replacement_pr_url": replacement_pr_url}, now)
            self._refresh_dependencies(conn, now)
            return self._task(conn.execute("SELECT * FROM tasks WHERE id=?", (source_task_id,)).fetchone())

    def get_agent(self, agent_id):
        with self._connection() as conn:
            return self._agent(conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone())

    def set_agent_state(self, agent_id, status, task_id=None):
        """Record an actual planner/reviewer process without claiming its task."""
        if status not in {"working", "idle"}:
            raise ValueError("Agent status must be working or idle")
        with self._connection(write=True) as conn:
            cursor = conn.execute("UPDATE agents SET status=?,task_id=?,last_seen=? WHERE id=?",
                                  (status, task_id if status == "working" else None, time.time(), agent_id))
            if not cursor.rowcount:
                raise KeyError(agent_id)

    def set_task_artifacts(self, task_id, branch=None, pr_url=None, actor="controller"):
        if pr_url is not None and not pr_url.startswith("https://"):
            raise ValueError("pr_url must be an HTTPS URL")
        with self._connection(write=True) as conn:
            cursor = conn.execute("UPDATE tasks SET branch=COALESCE(?,branch),pr_url=COALESCE(?,pr_url),updated_at=? WHERE id=?",
                                  (branch, pr_url, time.time(), task_id))
            if not cursor.rowcount:
                raise KeyError(task_id)
            self._event(conn, "task.artifacts", actor, "Linked review artifacts", task_id,
                        {"branch": branch, "pr_url": pr_url})

    def record_event(self, kind, actor, message, task_id=None, data=None):
        with self._connection(write=True) as conn:
            return self._event(conn, kind, actor, message, task_id, data)

    def record_benchmark(self, data):
        """Record a caller-supplied, real measurement; no results are synthesized."""
        if not isinstance(data, dict) or not data:
            raise ValueError("Benchmark data must be a nonempty object")
        with self._connection(write=True) as conn:
            now = time.time()
            cursor = conn.execute("INSERT INTO benchmarks(at,data) VALUES(?,?)", (now, _json(data)))
            self._event(conn, "benchmark.recorded", data.get("actor", "benchmark"), data.get("name", "Benchmark result recorded"),
                        data.get("task_id"), {"benchmark_id": cursor.lastrowid}, now)
            return cursor.lastrowid

    def record_review(self, data):
        if not isinstance(data, dict) or not data:
            raise ValueError("Review data must be a nonempty object")
        with self._connection(write=True) as conn:
            now = time.time()
            cursor = conn.execute("INSERT INTO reviews(at,data) VALUES(?,?)", (now, _json(data)))
            self._event(conn, "review.recorded", data.get("actor", "reviewer"), data.get("summary", "Review recorded"),
                        data.get("task_id"), {"review_id": cursor.lastrowid}, now)
            return cursor.lastrowid

    def snapshot(self, project=None):
        # An explicit read transaction keeps the whole snapshot consistent while workers write.
        with self._connection() as conn:
            conn.execute("BEGIN")
            tasks = [self._task(row) for row in conn.execute("SELECT * FROM tasks ORDER BY priority DESC,created_at,id")]
            agents = [self._agent(row) for row in conn.execute("SELECT * FROM agents ORDER BY id")]
            events = []
            for row in conn.execute("SELECT * FROM events ORDER BY id"):
                item = dict(row)
                item["at"] = timestamp(item["at"])
                item["data"] = json.loads(item["data"])
                events.append(item)
            records = {}
            for table in ("benchmarks", "reviews"):
                records[table] = [dict(json.loads(row["data"]), id=row["id"], at=timestamp(row["at"]))
                                  for row in conn.execute("SELECT * FROM " + table + " ORDER BY id")]
            conn.commit()
        result = {
            "schema_version": 1,
            "project": project or {"name": "QED Colony", "repo_url": "https://github.com/RSoulatIOHK/qed-colony",
                                   "mission": "Build a local, reproducible Lean tactic for complex program verification, with kernel-checked proofs."},
            "generated_at": timestamp(), "mode": "live", "agents": agents, "tasks": tasks,
            "events": events, "benchmarks": records["benchmarks"], "reviews": records["reviews"],
        }
        policy = getattr(self, "autonomy_policy", None)
        if policy is not None:
            from .autonomy_store import AutonomyStore
            autonomy = AutonomyStore(self.path).initialize()
            # Local process logs and checkout paths are never part of the public API.
            keys = {"id", "task_id", "role", "phase", "created_at", "updated_at", "branch", "pr_url",
                    "head_sha", "reviewed_sha", "revision", "review", "checks", "summary", "model",
                    "reasoning_effort", "model_reason", "author_model", "review_model", "last_error",
                    "ci_status", "ci_checks", "review_attempt", "governance_required",
                    "governance_status", "follow_up_task_ids", "recovery_kind", "recovery_root_id",
                    "recovery_owner", "recovery_status", "recovery_reason", "recovery_next_action",
                    "recovery_next_action_deadline", "recovery_triage_cycle_id", "recovery_repair_cycle_id",
                    "recovery_repair_task_id", "recovery_diagnosis", "recovery_replacement_pr_url",
                    "recovery_replacement_head_sha", "source_pr_url", "source_head_sha"}
            cycles = [{key: value for key, value in cycle.items() if key in keys}
                      for cycle in autonomy.list_cycles()]
            result["autonomy"] = {"service": autonomy.service_snapshot(),
                                  "budget": autonomy.get_budget(policy), "cycles": cycles}
            from .model_policy import DEFAULT_TIERS
            tiers = policy.get("model_tiers", list(DEFAULT_TIERS))
            result["autonomy"]["model_policy"] = {
                "tiers": tiers, "default_model": tiers[0]["model"],
                "default_reasoning_effort": tiers[0]["reasoning_effort"],
                "escalation": "Failed attempts and proof-sensitive reviews",
                "max_concurrency": policy.get("max_concurrency", 1),
            }
        return result
