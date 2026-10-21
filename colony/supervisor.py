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
from .network import AuthenticationFailure, NetworkUnavailable
from .network_recovery import due, schedule_retry


CONTROLLER_PHASES = frozenset({"publishing", "review_publication", "ci", "merging"})


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

        # Recovery ownership is deterministic and independent of both model
        # budget and the merge status of an operations audit.
        from .recovery import scan_recoveries
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        for root in self.autonomy.list_cycles():
            if root.get("recovery_status") == "repair_merged" and hasattr(self.pipeline, "reconcile_recovery"):
                self.pipeline.reconcile_recovery(root["id"])

        # Finish recorded publication/review/CI work before another bounded
        # model call can occupy this synchronous dispatcher for several minutes.
        # A pending check is polled once per pass, so it cannot starve models.
        controller_results = self._advance_controller_stages()
        cycle = self._next_cycle()
        if cycle is not None:
            if cycle["phase"] == "waiting_network":
                if not due(cycle):
                    return self._service("waiting_network", "Network unavailable; retry scheduled at %s" %
                                         cycle.get("next_retry_at"), cycle["id"])
                resume = cycle.get("resume_phase")
                if not resume:
                    self.autonomy.update_cycle(cycle["id"], phase="needs_review",
                                               last_error="Network wait has no saved resume phase")
                    return self._service("needs_review", "Network recovery state is incomplete", cycle["id"])
                try:
                    probe = getattr(self.pipeline, "probe_connectivity", None)
                    if probe is not None:
                        probe()
                except NetworkUnavailable:
                    current = self.autonomy.get_cycle(cycle["id"])
                    schedule_retry(current,
                                   lambda saved, phase, **data: self.autonomy.update_cycle(saved["id"], phase, **data),
                                   base_seconds=self.policy.get("network_backoff_base_seconds", 5),
                                   max_seconds=self.policy.get("network_backoff_max_seconds", 900))
                    return self._service("waiting_network", "Connectivity probe failed; retry rescheduled", cycle["id"])
                except AuthenticationFailure:
                    self.autonomy.update_cycle(cycle["id"], phase="needs_review",
                                               last_error="Remote authentication requires operator attention")
                    return self._service("needs_review", "Network recovery requires authentication attention", cycle["id"])
                cycle = self.autonomy.update_cycle(cycle["id"], phase=resume, resume_phase=None,
                                                   next_retry_at=None, network_retry_delay=None, last_error=None)
            return self._advance(cycle)

        if not controller_results:
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
        if controller_results:
            # Existing checks must not prevent admission of already-scoped
            # ready tasks, but they do suppress speculative audits/planning.
            return controller_results[-1]

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

    @staticmethod
    def _controller_stage(cycle):
        # Triage dispatch is selected by kind before phase in Pipeline.advance;
        # only its persisted handoff is guaranteed not to call a model.
        if cycle.get("recovery_kind") == "triage":
            return cycle["phase"] == "triage_handoff"
        return cycle["phase"] in CONTROLLER_PHASES

    @staticmethod
    def _schedule_order(cycle):
        return cycle.get("last_scheduled_order", 0), cycle["created_at"], cycle["id"]

    def _advance_controller_stages(self):
        results = []
        candidates = sorted((item for item in self.autonomy.list_cycles() if self._controller_stage(item)),
                            key=self._schedule_order)
        for recorded in candidates:
            cycle = self.autonomy.get_cycle(recorded["id"])
            # At most a saved review publication followed by one CI/merge step.
            # A phase that does not change is waiting for external state; it is
            # never retried inside this pass. New cycles wait for the next pass.
            for _ in range(2):
                if not self._controller_stage(cycle):
                    break
                phase = cycle["phase"]
                results.append(self._advance(cycle))
                cycle = self.autonomy.get_cycle(cycle["id"])
                if phase in {"ci", "merging"} or cycle["phase"] == phase:
                    break
        return results

    def _next_cycle(self):
        cycles = [item for item in self.autonomy.list_cycles()
                  if item["phase"] not in TERMINAL_PHASES and not self._controller_stage(item)]
        # Existing public candidates get their independent review before new
        # authorship. Each head has bounded review retries, so this finite queue
        # drains without an unbounded review convoy. Within each group, durable
        # round-robin order survives controller restarts.
        return min(cycles, key=lambda item: (item["phase"] != "reviewing", self._schedule_order(item))) if cycles else None

    def _advance(self, cycle):
        order = 1 + max((item.get("last_scheduled_order", 0) for item in self.autonomy.list_cycles()), default=0)
        cycle = self.autonomy.update_cycle(cycle["id"], last_scheduled_order=order)
        self._service("working", "Advancing " + cycle["phase"], cycle["id"])
        try:
            result = self.pipeline.advance(cycle)
        except BudgetExceeded as error:
            return self._service("budget_limited", str(error), cycle["id"])
        except Exception as error:
            # Round-robin scheduling means the oldest cycle may not be the
            # operation that failed. Park precisely the dispatched cycle.
            self.autonomy.update_cycle(cycle["id"], phase="needs_review", last_error=type(error).__name__)
            self.tasks.record_event("autonomy.error", "supervisor", "Controller operation requires review",
                                    cycle["task_id"], {"error_type": type(error).__name__})
            return self._service("needs_review", "Controller error: " + type(error).__name__)
        current = self.autonomy.get_cycle(cycle["id"])
        if current["phase"] == "waiting_network":
            return self._service("waiting_network", "Transient network outage; retry scheduled at %s" %
                                 current.get("next_retry_at"), cycle["id"])
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
                    self.tasks.record_event("autonomy.error", "supervisor", "Controller operation requires review",
                                            None,
                                            {"error_type": type(error).__name__})
                    self._service("needs_review", "Controller error: " + type(error).__name__)
                stop_event.wait(poll_seconds)
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=16)
            self._service("stopped", "Supervisor stopped; persisted work will be reconciled on restart")
            self.release_lock()
