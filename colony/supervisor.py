"""A restartable, single-controller dispatch loop.

The pipeline owns repository operations. This module only selects durable work,
enforces the controller singleton, and keeps service health visible.
"""

import fcntl
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import threading

from .autonomy_store import AutonomyStore, BudgetExceeded, CapacityUnavailable, TERMINAL_PHASES
from .store import Store
from .network import AuthenticationFailure, NetworkUnavailable
from .network_recovery import due, schedule_retry


CONTROLLER_PHASES = frozenset({"publishing", "review_publication", "ci", "merging"})
MODEL_PHASES = frozenset({"authoring", "reviewing", "triaging", "planning"})


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
        self._in_flight = {}
        self._completion = threading.Event()
        self._admission_stop = None

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
        if any(not future.done() for future in self._in_flight.values()):
            raise RuntimeError("Cannot release the controller lock while bounded model stages are running")
        self._reap_model_stages()
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

    def tick(self, executor=None):
        """Advance synchronously, or fill an explicitly supplied model pool.

        The service selects the pool path for concurrency greater than one.
        Repository publication and cached handoffs always stay on this caller.
        """
        if executor is not None:
            return self._parallel_tick(executor)
        if self._in_flight:
            raise RuntimeError("Concurrent model stages require the executor-backed tick path")
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
                    # Already-scoped Store work can still enter the queue; a
                    # future network deadline suppresses only speculative work.
                    self.tasks.recover_expired()
                    ready = self._ready_task()
                    if ready is not None:
                        budget = self.autonomy.get_budget(self.policy)
                        if budget["exhausted"]:
                            return self._service("budget_limited", "Daily model budget exhausted; resumes after " + budget["resets_at"])
                        return self._dispatch_task(ready)
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
        ready = self._ready_task()
        if ready is not None:
            return self._dispatch_task(ready)
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

    def _ready_task(self):
        dispatched = {item["task_id"] for item in self.autonomy.list_cycles()}
        # Store.snapshot orders highest priority, oldest task first.
        return next((task for task in self.tasks.snapshot()["tasks"]
                     if task["status"] == "ready" and task["id"] not in dispatched), None)

    def _dispatch_task(self, task):
        cycle = self.autonomy.create_cycle(task["id"], task["role"])
        self.tasks.record_event("autonomy.cycle_created", "supervisor", "Scheduled " + task["title"],
                                task["id"], {"cycle_id": cycle["id"]})
        return self._advance(cycle)

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
        candidates = sorted((item for item in self.autonomy.list_cycles()
                             if item["id"] not in self._in_flight and self._controller_stage(item)),
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

    def _next_cycle(self, excluded=()):
        cycles = [item for item in self.autonomy.list_cycles()
                  if item["id"] not in self._in_flight and item["id"] not in excluded
                  and item["phase"] not in TERMINAL_PHASES and not self._controller_stage(item)]
        # A persisted wait must not monopolize round-robin dispatch before
        # its deadline. Keep a waiting cycle for status reporting only when
        # every existing cycle is blocked; provider gating still lives in _job.
        eligible = [item for item in cycles if item["phase"] != "waiting_network" or due(item)]
        if eligible:
            cycles = eligible
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

    def _concurrency(self):
        limit = self.policy.get("max_concurrency", 1)
        if type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("max_concurrency must be an integer between 1 and 16")
        return limit

    def _reap_model_stages(self):
        results = []
        for cycle_id, future in list(self._in_flight.items()):
            if future.done():
                # The cycle remains excluded from controller work until the
                # complete future, including cleanup and error recording, ends.
                results.append((cycle_id, future.result()))
                del self._in_flight[cycle_id]
        return results

    def _execute_model_stage(self, cycle):
        """No publication, worktree preparation, or cached handoff runs here."""
        try:
            self.pipeline.advance_model(cycle)
        except BudgetExceeded as error:
            return {"status": "budget_limited", "message": str(error)}
        except CapacityUnavailable as error:
            return {"status": "capacity_limited", "message": str(error)}
        except Exception as error:
            self.autonomy.update_cycle(cycle["id"], phase="needs_review", last_error=type(error).__name__)
            self.tasks.record_event("autonomy.error", "supervisor", "Bounded model stage requires review",
                                    cycle["task_id"], {"error_type": type(error).__name__})
            return {"status": "needs_review", "message": "Model stage error: " + type(error).__name__}
        return {"status": "completed"}

    def _model_finished(self, future):
        # A denied reservation did not occupy a real worker. Wait for the normal
        # poll or another worker's completion instead of spinning on that denial.
        try:
            if future.result().get("status") in {"budget_limited", "capacity_limited"}:
                return
        except BaseException:
            pass
        self._completion.set()

    def _submit_model_stage(self, executor, cycle):
        order = 1 + max((item.get("last_scheduled_order", 0) for item in self.autonomy.list_cycles()), default=0)
        cycle = self.autonomy.update_cycle(cycle["id"], last_scheduled_order=order)
        future = executor.submit(self._execute_model_stage, cycle)
        self._in_flight[cycle["id"]] = future
        future.add_done_callback(self._model_finished)

    def _free_model_lanes(self, limit):
        budget = self.autonomy.get_budget(self.policy)
        tracked = set(self._in_flight)
        external = max(0, budget.get("active_attempts", 0) -
                       len(tracked.intersection(budget.get("active_cycle_ids", []))))
        return max(0, limit - len(tracked) - external - budget.get("uncertain_workers", 0))

    def _admission_stopped(self):
        return self._admission_stop is not None and self._admission_stop.is_set()

    def _resume_parallel_network(self, cycle):
        if not due(cycle):
            return cycle
        resume = cycle.get("resume_phase")
        if not resume:
            return self.autonomy.update_cycle(cycle["id"], phase="needs_review",
                                              last_error="Network wait has no saved resume phase")
        try:
            probe = getattr(self.pipeline, "probe_connectivity", None)
            if probe is not None:
                probe()
        except NetworkUnavailable:
            return schedule_retry(cycle,
                                  lambda saved, phase, **data: self.autonomy.update_cycle(saved["id"], phase, **data),
                                  base_seconds=self.policy.get("network_backoff_base_seconds", 5),
                                  max_seconds=self.policy.get("network_backoff_max_seconds", 900))
        except AuthenticationFailure:
            return self.autonomy.update_cycle(cycle["id"], phase="needs_review",
                                              last_error="Remote authentication requires operator attention")
        return self.autonomy.update_cycle(cycle["id"], phase=resume, resume_phase=None,
                                          next_retry_at=None, network_retry_delay=None, last_error=None)

    def _planner_refill_allowed(self):
        cycles = self.autonomy.list_cycles()
        if any(cycle["phase"] == "waiting_network" for cycle in cycles):
            return False
        planners = [cycle for cycle in cycles if cycle["role"] == "planner"]
        if any(cycle["phase"] not in TERMINAL_PHASES for cycle in planners):
            return False
        if planners and planners[-1]["phase"] in {"failed", "blocked", "needs_review"}:
            # A failed speculative plan is not an excuse to repeatedly spend
            # attempts. Reconsider only after subsequent mission work advances.
            last = planners[-1]["updated_at"]
            return any(cycle["role"] in {"engineer", "researcher"} and cycle["updated_at"] > last
                       for cycle in cycles)
        return True

    def _parallel_tick(self, executor):
        self.startup()
        limit = self._concurrency()
        completed = self._reap_model_stages()
        if not self.policy.get("enabled", False):
            return self._service("disabled", "Autonomy is disabled in controller policy")

        from .recovery import scan_recoveries
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        for root in self.autonomy.list_cycles():
            if (root["id"] not in self._in_flight and root.get("recovery_status") == "repair_merged"
                    and hasattr(self.pipeline, "reconcile_recovery")):
                self.pipeline.reconcile_recovery(root["id"])
        for cycle in self.autonomy.list_cycles():
            if (cycle["id"] not in self._in_flight and cycle["phase"] == "waiting_network"
                    and self._controller_stage(dict(cycle, phase=cycle.get("resume_phase")))):
                # A full model pool cannot delay reconnecting a saved
                # publication/CI/handoff stage; it consumes no model lane.
                self._resume_parallel_network(cycle)
        controller_results = self._advance_controller_stages()
        self.tasks.recover_expired()

        # Exclude denied calls for this pass. Atomic reservation is the authority
        # on budgets and uncertain workers, including processes from a restart.
        visited = {cycle_id for cycle_id, result in completed
                   if result.get("status") in {"budget_limited", "capacity_limited"}}
        planner_considered = False
        while not self._admission_stopped() and self._free_model_lanes(limit):
            cycle = self._next_cycle(excluded=visited)
            if cycle is None:
                budget = self.autonomy.get_budget(self.policy)
                if budget["exhausted"]:
                    break
                ready = self._ready_task()
                if ready is not None:
                    cycle = self.autonomy.create_cycle(ready["id"], ready["role"])
                    self.tasks.record_event("autonomy.cycle_created", "supervisor", "Scheduled " + ready["title"],
                                            ready["id"], {"cycle_id": cycle["id"]})
                elif not planner_considered:
                    planner_considered = True
                    active = [item for item in self.autonomy.list_cycles() if item["phase"] not in TERMINAL_PHASES]
                    if not self._in_flight and not controller_results and not active:
                        # Preserve periodic stewardship only at genuine idle
                        # admission boundaries, never to fill spare mission lanes.
                        from .operations import maybe_enqueue_audit
                        maybe_enqueue_audit(self.tasks, self.autonomy, self.policy)
                        ready = self._ready_task()
                        if ready is not None:
                            cycle = self.autonomy.create_cycle(ready["id"], ready["role"])
                            self.tasks.record_event("autonomy.cycle_created", "supervisor", "Scheduled " + ready["title"],
                                                    ready["id"], {"cycle_id": cycle["id"]})
                    if cycle is None:
                        if not self._planner_refill_allowed():
                            break
                        try:
                            cycle = self.pipeline.prepare_plan()
                        except BudgetExceeded:
                            break
                    if cycle is None:
                        break
                else:
                    break
            visited.add(cycle["id"])
            if cycle["phase"] == "waiting_network":
                cycle = self._resume_parallel_network(cycle)
            if cycle["phase"] in TERMINAL_PHASES or cycle["phase"] == "waiting_network":
                continue
            if self._controller_stage(cycle):
                # A network wait may have resumed a publication or CI stage.
                controller_results.append(self._advance(cycle))
                continue
            if cycle["phase"] == "queued":
                # Queued authors and planners prepare their separate worktrees
                # on the controller before occupying a model lane.
                if cycle["role"] == "planner":
                    try:
                        prepared = self.pipeline.prepare_plan(cycle=cycle)
                    except BudgetExceeded:
                        continue
                    if prepared is None:
                        continue
                    cycle = prepared
                elif cycle.get("recovery_kind") == "triage":
                    cycle = self.autonomy.update_cycle(cycle["id"], phase="triaging")
                else:
                    controller_results.append(self._advance(cycle))
                    cycle = self.autonomy.get_cycle(cycle["id"])
            if cycle["phase"] not in MODEL_PHASES:
                continue
            try:
                cycle = self.pipeline.prepare_model_cycle(cycle)
            except BudgetExceeded:
                continue
            if cycle["phase"] in MODEL_PHASES and not self._admission_stopped():
                self._submit_model_stage(executor, cycle)

        completed.extend(self._reap_model_stages())
        if self._in_flight:
            count = len(self._in_flight)
            return self._service("working", "%d model stage%s in flight (limit %d); controller handoffs remain serial" %
                                 (count, "" if count == 1 else "s", limit))
        limited = next((result for _, result in completed
                        if result.get("status") in {"budget_limited", "capacity_limited"}), None)
        if limited:
            return self._service(limited["status"], limited["message"])
        budget = self.autonomy.get_budget(self.policy)
        if budget["exhausted"]:
            return self._service("budget_limited", "Daily model budget exhausted; resumes after " + budget["resets_at"])
        if not self._free_model_lanes(limit):
            return self._service("capacity_limited", "Model lanes are held by recorded or uncertain workers; reconcile their ownership before new admission")
        waiting = [cycle for cycle in self.autonomy.list_cycles() if cycle["phase"] == "waiting_network"]
        if waiting:
            return self._service("waiting_network", "Network retry deadlines are persisted; no model stage is in flight")
        if controller_results:
            return controller_results[-1]
        return self._service("waiting", "Healthy; no runnable model stage or ready scoped work")

    def run_forever(self, stop_event=None, poll_seconds=None):
        stop_event = stop_event or threading.Event()
        poll_seconds = self.policy.get("poll_seconds", 30) if poll_seconds is None else poll_seconds
        if isinstance(poll_seconds, bool) or not isinstance(poll_seconds, (int, float)) or not 0 < poll_seconds <= 60:
            raise ValueError("poll_seconds must be between 0 and 60")
        concurrency = self._concurrency()
        self.startup()
        self._admission_stop = stop_event
        heartbeat_stop = threading.Event()

        def keepalive():
            while not heartbeat_stop.wait(min(30, poll_seconds)):
                self.autonomy.heartbeat_service(os.getpid())

        heartbeat = threading.Thread(target=keepalive, name="colony-supervisor-heartbeat", daemon=True)
        heartbeat.start()
        executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="colony-model") if concurrency > 1 else None
        try:
            while not stop_event.is_set():
                self._completion.clear()
                try:
                    self.tick(executor=executor)
                except Exception as error:
                    # Unexpected failures must remain visible and must not
                    # automatically repeat a potentially mutating operation.
                    self.tasks.record_event("autonomy.error", "supervisor", "Controller operation requires review",
                                            None,
                                            {"error_type": type(error).__name__})
                    self._service("needs_review", "Controller error: " + type(error).__name__)
                if executor is None:
                    stop_event.wait(poll_seconds)
                else:
                    # Completion wakes the loop immediately; short stop checks
                    # avoid waiting a full poll interval for graceful shutdown.
                    waited = 0.0
                    while not stop_event.is_set() and not self._completion.is_set() and waited < poll_seconds:
                        interval = min(0.1, poll_seconds - waited)
                        self._completion.wait(interval)
                        waited += interval
        finally:
            if executor is not None:
                self._service("draining", "Stopping admission; waiting for bounded model stages before releasing the controller lock")
                executor.shutdown(wait=True)
                self._reap_model_stages()
            heartbeat_stop.set()
            heartbeat.join(timeout=16)
            self._service("stopped", "Supervisor stopped; persisted work will be reconciled on restart")
            self.release_lock()
            self._admission_stop = None
