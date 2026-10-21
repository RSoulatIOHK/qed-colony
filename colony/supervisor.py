"""A restartable, single-controller dispatch loop.

The pipeline owns repository operations. This module only selects durable work,
enforces the controller singleton, and keeps service health visible.
"""

import fcntl
import os
from pathlib import Path
import threading

from .autonomy_store import AutonomyStore, BudgetExceeded, TERMINAL_PHASES
from .store import Store


class SupervisorAlreadyRunning(RuntimeError):
    """Another process owns this database's supervisor lock."""


class Supervisor:
    def __init__(self, root, db_path, policy, pipeline=None, task_store=None):
        self.root = Path(root).resolve()
        self.db_path = Path(db_path).resolve()
        self.policy = dict(policy or {})
        self.tasks = task_store or Store(self.db_path).initialize()
        self.autonomy = AutonomyStore(self.db_path).initialize()
        if pipeline is None:
            from .pipeline import Pipeline
            pipeline = Pipeline(self.root, self.tasks, self.autonomy, self.policy)
        self.pipeline = pipeline
        self._lock = None
        self._started = False

    @property
    def lock_path(self):
        return self.db_path.with_name(self.db_path.name + ".supervisor.lock")

    def acquire_lock(self):
        if self._lock is not None:
            return self
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            stream.close()
            raise SupervisorAlreadyRunning("A supervisor already owns this database")
        stream.seek(0)
        stream.truncate()
        stream.write(str(os.getpid()) + "\n")
        stream.flush()
        self._lock = stream
        return self

    def release_lock(self):
        if self._lock is not None:
            fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
            self._lock.close()
            self._lock = None
        self._started = False

    def __enter__(self):
        return self.acquire_lock()

    def __exit__(self, exc_type, exc, traceback):
        self.release_lock()

    def _service(self, status, message, cycle=None):
        self.autonomy.set_service(status, os.getpid(), cycle, message)
        return {"status": status, "message": message, "active_cycle": cycle}

    def startup(self):
        """Reconcile only after taking the exclusive, OS-released process lock."""
        self.acquire_lock()
        if not self._started:
            recovered = self.autonomy.reconcile_interrupted()
            for attempt in recovered:
                cycle = self.autonomy.get_cycle(attempt["cycle_id"])
                self.tasks.record_event("autonomy.interrupted", "supervisor",
                                        "Interrupted model attempt requires review; reservation retained",
                                        cycle["task_id"], {"cycle_id": cycle["id"], "stage": attempt["stage"]})
            self._started = True
            self._service("waiting", "Supervisor ready; durable state reconciled")
        return self

    def tick(self):
        self.startup()
        if not self.policy.get("enabled", False):
            return self._service("disabled", "Autonomy is disabled in controller policy")

        # Advancing an existing cycle can poll CI or reconcile a published PR
        # without spending model budget. The pipeline reserves each model call.
        cycle = self.autonomy.next_cycle()
        if cycle is not None:
            return self._advance(cycle)

        from .operations import maybe_enqueue_audit
        maybe_enqueue_audit(self.tasks, self.autonomy, self.policy)

        budget = self.autonomy.get_budget(self.policy)
        if budget["exhausted"]:
            return self._service("budget_limited", "Daily model budget exhausted; resumes after " + budget["resets_at"])

        self.tasks.recover_expired()
        cycles = self.autonomy.list_cycles()
        already_dispatched = {item["task_id"] for item in cycles}
        ready = [task for task in self.tasks.snapshot()["tasks"]
                 if task["status"] == "ready" and task["id"] not in already_dispatched]
        if ready:
            # Store.snapshot already orders highest priority, oldest task first.
            task = ready[0]
            cycle = self.autonomy.create_cycle(task["id"], task["role"])
            self.tasks.record_event("autonomy.cycle_created", "supervisor", "Scheduled " + task["title"],
                                    task["id"], {"cycle_id": cycle["id"]})
            return self._advance(cycle)

        # Planning itself is a bounded pipeline operation. No speculative task
        # or agent activity is recorded merely because this poll ran.
        try:
            result = self.pipeline.plan()
        except BudgetExceeded as error:
            return self._service("budget_limited", str(error))
        if result and result.get("status") in {"planned", "created", "ready"}:
            return self._service("waiting", "New bounded work is ready for the next dispatch")
        needs_review = any(item["phase"] == "needs_review" for item in cycles)
        message = "Waiting for review of interrupted work" if needs_review else "Healthy; waiting for runnable work or the next planning interval"
        return self._service("waiting", message)

    def _advance(self, cycle):
        self._service("working", "Advancing " + cycle["phase"], cycle["id"])
        try:
            result = self.pipeline.advance(cycle)
        except BudgetExceeded as error:
            return self._service("budget_limited", str(error), cycle["id"])
        current = self.autonomy.get_cycle(cycle["id"])
        if current["phase"] in TERMINAL_PHASES:
            status = "needs_review" if current["phase"] in {"needs_review", "blocked"} else "waiting"
            return self._service(status, "Cycle " + current["phase"], None)
        result = result if isinstance(result, dict) else {}
        message = result.get("message", "Cycle waiting at " + current["phase"])
        return self._service("working", message, cycle["id"])

    def run_forever(self, stop_event=None, poll_seconds=None):
        stop_event = stop_event or threading.Event()
        poll_seconds = self.policy.get("poll_seconds", 30) if poll_seconds is None else poll_seconds
        if isinstance(poll_seconds, bool) or not isinstance(poll_seconds, (int, float)) or not 0 < poll_seconds <= 60:
            raise ValueError("poll_seconds must be between 0 and 60")
        self.startup()
        heartbeat_stop = threading.Event()

        def keepalive():
            while not heartbeat_stop.wait(min(30, poll_seconds)):
                self.autonomy.heartbeat_service(os.getpid())

        heartbeat = threading.Thread(target=keepalive, name="colony-supervisor-heartbeat", daemon=True)
        heartbeat.start()
        try:
            while not stop_event.is_set():
                try:
                    self.tick()
                except Exception as error:
                    # Unexpected failures must remain visible and must not
                    # automatically repeat a potentially mutating operation.
                    cycle = self.autonomy.next_cycle()
                    if cycle is not None:
                        self.autonomy.update_cycle(cycle["id"], phase="needs_review",
                                                   last_error=type(error).__name__)
                    self.tasks.record_event("autonomy.error", "supervisor", "Controller operation requires review",
                                            cycle["task_id"] if cycle else None,
                                            {"error_type": type(error).__name__})
                    self._service("needs_review", "Controller error: " + type(error).__name__)
                stop_event.wait(poll_seconds)
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=16)
            self._service("stopped", "Supervisor stopped; persisted work will be reconciled on restart")
            self.release_lock()
