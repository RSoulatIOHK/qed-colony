"""Real pipeline concurrency with blocked executors, not simulated model time.

The acceptance boundary is overlapping independent model calls with a shared
transactional ledger, while publication, review handoff, and merge stay on one
controller. Events and barriers make the ordering assertions independent of
worker speed; the fixtures never call a model provider or GitHub.
"""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from colony.autonomy_store import AutonomyStore, BudgetExceeded, CapacityUnavailable, DuplicateAttempt
from colony.pipeline import Pipeline
from colony.recovery import apply_triage_result, scan_recoveries
from colony.store import Store
from colony.supervisor import Supervisor, SupervisorAlreadyRunning


class BlockingExecutor:
    def __init__(self):
        self.condition = threading.Condition()
        self.calls = []
        self.active = set()
        self.max_active = 0
        self.overlapping_same_task = False
        self.releases = {}
        self.open = False
        self.worktrees = {}

    def __call__(self, root, worktree, prompt, timeout, sandbox, agent_id, **kwargs):
        task_id = self.worktrees[str(worktree)]
        stage = agent_id.split("-")[1]
        key = (task_id, stage)
        with self.condition:
            release = self.releases.setdefault(key, threading.Event())
            if self.open:
                release.set()
            if any(active[0] == task_id for active in self.active):
                self.overlapping_same_task = True
            self.active.add(key)
            self.calls.append({"task_id": task_id, "stage": stage, "sandbox": sandbox,
                               "prompt": prompt, "thread": threading.get_ident()})
            self.max_active = max(self.max_active, len(self.active))
            self.condition.notify_all()
        try:
            if not release.wait(10):
                raise AssertionError("Test did not release bounded executor " + str(key))
            if stage == "review":
                summary = json.dumps({"verdict": "approve", "summary": "Exact candidate checked",
                                      "findings": []})
            elif stage == "planner":
                summary = json.dumps({"tasks": [{"title": "Independent planned investigation",
                                      "role": "researcher", "description": "Inspect one falsifiable proof question.",
                                      "acceptance": ["Record an actual observation and limitations"]}]})
            elif stage == "triage":
                summary = json.dumps({"action": "escalate", "diagnosis": "Requires separately scoped controller work.",
                                      "repair_title": "", "repair_description": "", "role": ""})
            else:
                summary = "Scoped implementation complete; deterministic fixture check passed."
            return {"status": "completed", "summary": summary, "elapsed_seconds": 1}
        finally:
            with self.condition:
                self.active.remove(key)
                self.condition.notify_all()

    def wait_for_calls(self, count):
        with self.condition:
            return self.condition.wait_for(lambda: len(self.calls) >= count, timeout=5)

    def wait_for_stage(self, task_id, stage):
        with self.condition:
            return self.condition.wait_for(lambda: any(call["task_id"] == task_id and call["stage"] == stage
                                                      for call in self.calls), timeout=5)

    def release(self, task_id, stage):
        with self.condition:
            self.releases[(task_id, stage)].set()

    def release_all(self):
        with self.condition:
            self.open = True
            for release in self.releases.values():
                release.set()


class ParallelBroker:
    def __init__(self, root, executor):
        self.root = root
        self.executor = executor
        self.prs = {}
        self.by_task = {}
        self.controller_operations = []

    def _controller(self, operation, task_id):
        self.controller_operations.append((operation, task_id, threading.get_ident()))

    def prepare_worktree(self, cycle):
        self._controller("prepare", cycle["task_id"])
        worktree = self.root / "cycles" / cycle["id"]
        worktree.mkdir(parents=True, exist_ok=True)
        self.executor.worktrees[str(worktree)] = cycle["task_id"]
        return {"worktree": str(worktree), "branch": "codex/test-" + cycle["id"],
                "base_sha": "b" * 40}

    def validate_changes(self, *args):
        return ["lean/Colony/Examples/ParallelFixture.lean"]

    def commit(self, cycle, task):
        self._controller("commit", task["id"])
        return hashlib.sha1(task["id"].encode("utf-8")).hexdigest()

    def publish(self, cycle, task, summary):
        self._controller("publish", task["id"])
        number = len(self.prs) + 1
        pr = {"number": number, "url": "https://github.com/example/repo/pull/%s" % number,
              "state": "OPEN", "headRefOid": cycle["head_sha"],
              "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
              "statusCheckRollup": [{"name": name, "status": "COMPLETED", "conclusion": "SUCCESS"}
                                    for name in ["control-plane", "lean-seed"]]}
        self.prs[number] = pr
        self.by_task[task["id"]] = number
        return pr

    def get_pr(self, number):
        return self.prs[number]

    def comment_review(self, number, review, sha, cycle_id):
        task_id = next(task for task, candidate in self.by_task.items() if candidate == number)
        self._controller("review", task_id)
        if sha != self.prs[number]["headRefOid"]:
            raise AssertionError("Review publication changed the candidate head")

    def merge(self, number, sha):
        task_id = next(task for task, candidate in self.by_task.items() if candidate == number)
        self._controller("merge", task_id)
        if sha != self.prs[number]["headRefOid"]:
            raise AssertionError("Merge did not use the reviewed candidate head")
        self.prs[number].update(state="MERGED", mergedAt="2026-10-21T12:00:00Z")
        return self.prs[number]


class ParallelSupervisorTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.db"
        self.tasks = Store(self.path).initialize()
        self.autonomy = AutonomyStore(self.path).initialize()
        self.policy = {"enabled": True, "max_concurrency": 4,
                       "max_daily_seconds": 1000, "max_daily_attempts": 30,
                       "author_timeout_seconds": 10, "review_timeout_seconds": 10,
                       "planner_timeout_seconds": 10, "automatic_publication": True,
                       "automatic_merge": True, "max_revisions": 0,
                       "operations_audit_enabled": False}
        self.executor = BlockingExecutor()
        self.broker = ParallelBroker(self.root, self.executor)
        self.pipeline = Pipeline(self.root, self.tasks, self.autonomy, self.policy,
                                 broker=self.broker, executor=self.executor)
        self.supervisor = Supervisor(self.root, self.path, self.policy, self.pipeline, self.tasks)
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.addCleanup(self.supervisor.release_lock)
        self.addCleanup(self.pool.shutdown, wait=True)
        self.addCleanup(self.executor.release_all)
        provider = patch("colony.pipeline.probe_model_connectivity", return_value=True)
        provider.start()
        self.addCleanup(provider.stop)

    def seed(self, count, prefix="T"):
        self.tasks.seed([{"id": prefix + str(index), "title": "Scoped proof step " + str(index),
                          "description": "A separate bounded proof engineering task.",
                          "role": "engineer", "priority": 100 - index,
                          "acceptance": ["Preserve and prove the original specified theorem"]}
                         for index in range(count)])

    def tick(self):
        return self.supervisor.tick(executor=self.pool)

    def finish(self, task_id, stage):
        cycle = next(item for item in self.autonomy.list_cycles() if item["task_id"] == task_id)
        future = self.supervisor._in_flight[cycle["id"]]
        self.executor.release(task_id, stage)
        future.result(timeout=5)

    def test_four_authors_overlap_without_dispatching_a_fifth_or_repeating_one(self):
        self.seed(5)
        self.tick()
        self.assertTrue(self.executor.wait_for_calls(4), "Four independent authors never overlapped")
        with self.executor.condition:
            self.assertEqual(len(self.executor.active), 4)
            self.assertEqual(self.executor.max_active, 4)
            self.assertEqual({call["task_id"] for call in self.executor.calls}, {"T0", "T1", "T2", "T3"})
        self.tick()
        self.tick()
        self.assertEqual(len(self.executor.calls), 4)
        self.assertEqual(self.tasks.get_task("T4")["status"], "ready")
        attempts = self.autonomy.list_attempts()
        self.assertEqual(len(attempts), 4)
        self.assertEqual({item["status"] for item in attempts}, {"running"})
        self.assertEqual(self.autonomy.get_budget(self.policy)["reserved_seconds"], 40)

    def test_ready_task_is_admitted_while_an_existing_author_is_still_blocked(self):
        self.seed(1)
        self.tick()
        self.assertTrue(self.executor.wait_for_stage("T0", "author"))
        self.seed(1, prefix="INDEPENDENT")
        self.tick()
        self.assertTrue(self.executor.wait_for_stage("INDEPENDENT0", "author"),
                        "Existing author monopolized independent admission")
        with self.executor.condition:
            mission_active = {key for key in self.executor.active if key[1] != "planner"}
            self.assertEqual(mission_active, {("T0", "author"), ("INDEPENDENT0", "author")})
        task_ids = [cycle["task_id"] for cycle in self.autonomy.list_cycles()]
        self.assertEqual(task_ids.count("T0"), 1)
        self.assertEqual(task_ids.count("INDEPENDENT0"), 1)
        self.assertEqual(len([attempt for attempt in self.autonomy.list_attempts()
                              if attempt["stage"].startswith("author:")]), 2)

    def test_publication_review_and_merge_advance_while_another_author_is_blocked(self):
        self.seed(2)
        self.tick()
        self.assertTrue(self.executor.wait_for_stage("T0", "author"))
        self.assertTrue(self.executor.wait_for_stage("T1", "author"))
        self.finish("T0", "author")
        self.tick()
        self.assertTrue(self.executor.wait_for_stage("T0", "review"),
                        "Completed author did not reach independent review")
        with self.executor.condition:
            mission_active = {key for key in self.executor.active if key[1] != "planner"}
            self.assertEqual(mission_active, {("T1", "author"), ("T0", "review")})
            self.assertFalse(self.executor.overlapping_same_task)
            review = next(call for call in self.executor.calls if call["stage"] == "review")
        candidate = self.broker.prs[self.broker.by_task["T0"]]
        self.assertEqual(review["sandbox"], "read-only")
        self.assertIn(candidate["headRefOid"], review["prompt"])
        self.tick()
        self.assertEqual(len([call for call in self.executor.calls if call["stage"] == "review"]), 1,
                         "A pending review was dispatched twice")
        self.finish("T0", "review")
        self.tick()
        self.assertEqual(candidate["state"], "MERGED")
        self.assertEqual(self.tasks.get_task("T0")["status"], "done")
        self.assertEqual(self.tasks.get_task("T1")["status"], "running")
        self.assertEqual({thread_id for _, _, thread_id in self.broker.controller_operations},
                         {threading.get_ident()}, "A worker published or merged outside the controller")
        self.assertEqual([operation for operation, task, _ in self.broker.controller_operations if task == "T0"],
                         ["prepare", "commit", "publish", "review", "merge"])

    def test_single_planner_refills_a_spare_lane_while_original_author_remains_active(self):
        self.seed(1)
        self.tick()
        self.assertTrue(self.executor.wait_for_stage("T0", "author"))
        planner, = [cycle for cycle in self.autonomy.list_cycles() if cycle["role"] == "planner"]
        self.assertTrue(self.executor.wait_for_stage(planner["task_id"], "planner"))
        self.tick()
        self.tick()
        self.assertEqual(len([call for call in self.executor.calls if call["stage"] == "planner"]), 1,
                         "Spare capacity duplicated an existing planner")
        with self.executor.condition:
            self.assertEqual(self.executor.active, {("T0", "author"), (planner["task_id"], "planner")})
        self.finish(planner["task_id"], "planner")
        planned = self.autonomy.get_cycle(planner["id"])
        task_id, = planned["planned_task_ids"]
        self.tick()
        self.assertTrue(self.executor.wait_for_stage(task_id, "author"),
                        "A planned independent task waited for the original author to finish")
        with self.executor.condition:
            mission_active = {key for key in self.executor.active if key[1] != "planner"}
            self.assertEqual(mission_active, {("T0", "author"), (task_id, "author")})
            self.assertLessEqual(sum(stage == "planner" for _, stage in self.executor.active), 1)
        self.assertEqual(self.tasks.get_task("T0")["status"], "running")
        self.assertEqual(self.tasks.get_task(task_id)["status"], "running")
        self.assertEqual(len(self.autonomy.list_attempts(planner["id"])), 1)

    def test_queued_planner_prepares_on_controller_and_executes_in_a_model_lane(self):
        planner = self.autonomy.create_cycle("QUEUED-PLAN", "planner")
        self.assertEqual(planner["phase"], "queued")
        self.tick()
        self.assertTrue(self.executor.wait_for_stage("QUEUED-PLAN", "planner"))
        with self.executor.condition:
            call, = [call for call in self.executor.calls if call["task_id"] == "QUEUED-PLAN"]
            self.assertNotEqual(call["thread"], threading.get_ident(),
                                "Queued planner blocked the controller with inline inference")
        self.assertIn(planner["id"], self.supervisor._in_flight)
        self.assertEqual(len(self.autonomy.list_attempts(planner["id"])), 1)
        self.assertEqual(self.autonomy.get_cycle(planner["id"])["phase"], "planning")
        self.tick()
        self.assertEqual(len([call for call in self.executor.calls if call["task_id"] == "QUEUED-PLAN"]), 1)
        self.assertEqual({thread_id for _, _, thread_id in self.broker.controller_operations},
                         {threading.get_ident()})
        self.finish("QUEUED-PLAN", "planner")
        self.assertEqual(self.autonomy.get_cycle(planner["id"])["phase"], "done")

    def test_queued_triage_uses_model_lane_then_controller_applies_saved_handoff(self):
        self.tasks.seed([{"id": "ORIGINAL", "title": "Original required proof behavior", "role": "engineer",
                          "description": "Implement the full original behavior without weakening the theorem.",
                          "acceptance": ["Original theorem proved", "Invalid original case rejected"],
                          "status": "blocked"}])
        source = self.autonomy.create_cycle("ORIGINAL", "engineer")
        source_url = "https://github.com/example/repo/pull/7"
        self.broker.prs[7] = {"number": 7, "url": source_url, "state": "OPEN", "headRefOid": "a" * 40}
        self.autonomy.update_cycle(source["id"], phase="needs_review", pr_number=7,
                                   pr_url=source_url, head_sha="a" * 40,
                                   last_error="Original acceptance remains unsatisfied")
        scan_recoveries(self.tasks, self.autonomy, self.policy)
        triage = self.autonomy.get_cycle(self.autonomy.get_cycle(source["id"])["recovery_triage_cycle_id"])
        self.autonomy.update_cycle(triage["id"], phase="queued")
        handoff_threads = []

        def apply_on_controller(*args, **kwargs):
            handoff_threads.append(threading.get_ident())
            return apply_triage_result(*args, **kwargs)

        with patch("colony.pipeline.apply_triage_result", side_effect=apply_on_controller):
            self.tick()
            self.assertTrue(self.executor.wait_for_stage(triage["task_id"], "triage"))
            with self.executor.condition:
                call, = [call for call in self.executor.calls if call["task_id"] == triage["task_id"]]
                self.assertNotEqual(call["thread"], threading.get_ident(),
                                    "Queued triage blocked the controller with inline inference")
            self.assertIn(triage["id"], self.supervisor._in_flight)
            self.assertEqual(len(self.autonomy.list_attempts(triage["id"])), 1)
            self.assertEqual(handoff_threads, [])
            self.finish(triage["task_id"], "triage")
            self.assertEqual(self.autonomy.get_cycle(triage["id"])["phase"], "triage_handoff")
            self.assertEqual(handoff_threads, [], "Model worker applied controller-owned triage handoff")
            self.assertNotEqual(self.autonomy.get_cycle(source["id"])["recovery_status"], "escalated")
            self.tick()
            self.assertEqual(handoff_threads, [threading.get_ident()])
            self.assertEqual(self.autonomy.get_cycle(triage["id"])["phase"], "done")
            self.assertEqual(self.autonomy.get_cycle(source["id"])["recovery_status"], "escalated")
            self.assertEqual(self.tasks.get_task("ORIGINAL")["status"], "blocked")
            self.assertEqual(len(self.autonomy.list_attempts(triage["id"])), 1)
        self.assertEqual({thread_id for _, _, thread_id in self.broker.controller_operations},
                         {threading.get_ident()})

    def test_approved_ci_candidate_merges_even_when_all_four_model_lanes_are_busy(self):
        self.seed(4)
        self.tick()
        self.assertTrue(self.executor.wait_for_calls(4))
        self.tasks.seed([{"id": "APPROVED", "title": "Already reviewed independent candidate",
                          "role": "engineer", "status": "review"}])
        cycle = self.autonomy.create_cycle("APPROVED", "engineer")
        context = self.broker.prepare_worktree(cycle)
        task = self.tasks.get_task("APPROVED")
        sha = self.broker.commit(cycle, task)
        candidate = self.broker.publish(dict(cycle, head_sha=sha), task, "Existing reviewed artifact")
        self.autonomy.update_cycle(cycle["id"], phase="ci", head_sha=sha, reviewed_sha=sha,
                                   review={"verdict": "approve", "summary": "Verified", "findings": []},
                                   pr_number=candidate["number"], pr_url=candidate["url"], **context)
        self.tick()
        self.assertEqual(candidate["state"], "MERGED")
        self.assertEqual(self.tasks.get_task("APPROVED")["status"], "done")
        with self.executor.condition:
            self.assertEqual(len(self.executor.active), 4)
        self.assertEqual(len(self.autonomy.list_attempts()), 4)
        self.assertEqual({thread_id for _, _, thread_id in self.broker.controller_operations},
                         {threading.get_ident()})

    def test_due_network_ci_resumes_and_merges_while_all_four_model_lanes_are_busy(self):
        self.seed(4)
        self.tick()
        self.assertTrue(self.executor.wait_for_calls(4))
        self.tasks.seed([{"id": "APPROVED", "title": "Already reviewed independent candidate",
                          "role": "engineer", "status": "review"}])
        cycle = self.autonomy.create_cycle("APPROVED", "engineer")
        context = self.broker.prepare_worktree(cycle)
        task = self.tasks.get_task("APPROVED")
        sha = self.broker.commit(cycle, task)
        candidate = self.broker.publish(dict(cycle, head_sha=sha), task, "Existing reviewed artifact")
        self.autonomy.update_cycle(cycle["id"], phase="waiting_network", resume_phase="ci", next_retry_at=0,
                                   head_sha=sha, reviewed_sha=sha,
                                   review={"verdict": "approve", "summary": "Verified", "findings": []},
                                   pr_number=candidate["number"], pr_url=candidate["url"], **context)
        self.tick()
        self.assertEqual(candidate["state"], "MERGED")
        self.assertEqual(self.tasks.get_task("APPROVED")["status"], "done")
        with self.executor.condition:
            self.assertEqual(len(self.executor.active), 4)
        self.assertEqual(len(self.autonomy.list_attempts()), 4)
        self.assertEqual({thread_id for _, _, thread_id in self.broker.controller_operations},
                         {threading.get_ident()})

    def test_uncertain_workers_hold_all_lanes_without_a_healthy_or_working_claim(self):
        from colony.worker import _mark_uncertain_slot, _reserve_slot
        self.seed(1)
        for index in range(4):
            run_id = "uncertain-%s" % index
            _reserve_slot(self.path, run_id, 4, 10)
            _mark_uncertain_slot(self.path, run_id)
        result = self.tick()
        self.assertEqual(result["status"], "capacity_limited")
        self.assertIn("uncertain", result["message"])
        self.assertEqual(self.autonomy.get_budget(self.policy)["uncertain_workers"], 4)
        self.assertEqual(self.autonomy.list_attempts(), [])
        self.assertEqual(self.executor.calls, [])

    def test_graceful_stop_drains_four_workers_before_releasing_controller_lock(self):
        self.seed(4)
        stop = threading.Event()
        errors = []

        def run():
            try:
                self.supervisor.run_forever(stop_event=stop, poll_seconds=0.01)
            except BaseException as error:
                errors.append(error)

        controller = threading.Thread(target=run, name="test-parallel-controller", daemon=True)
        controller.start()

        def stop_controller():
            stop.set()
            self.executor.release_all()
            controller.join(timeout=5)

        self.addCleanup(stop_controller)
        self.assertTrue(self.executor.wait_for_calls(4))
        stop.set()
        second = Supervisor(self.root, self.path, self.policy, self.pipeline, self.tasks)
        self.addCleanup(second.release_lock)
        with self.assertRaises(SupervisorAlreadyRunning):
            second.startup()
        self.assertTrue(controller.is_alive())
        self.executor.release_all()
        controller.join(timeout=5)
        self.assertFalse(controller.is_alive(), "Graceful shutdown did not drain completed workers")
        self.assertEqual(errors, [])
        self.assertEqual(len(self.executor.calls), 4, "Shutdown launched additional model work")
        attempts = self.autonomy.list_attempts()
        self.assertEqual(len(attempts), 4)
        self.assertEqual({item["status"] for item in attempts}, {"completed"})
        self.assertEqual(self.autonomy.get_budget(self.policy)["reserved_seconds"], 0)
        second.startup()
        self.assertEqual({item["phase"] for item in self.autonomy.list_cycles()}, {"publishing"})
        self.assertEqual(len(self.autonomy.list_attempts()), 4)

    def test_stop_during_controller_preparation_does_not_launch_a_new_model(self):
        self.seed(1)
        stop = threading.Event()
        preparing = threading.Event()
        release_preparation = threading.Event()
        original_prepare = self.broker.prepare_worktree
        errors = []

        def prepare(cycle):
            preparing.set()
            if not release_preparation.wait(5):
                raise AssertionError("Test did not release controller preparation")
            return original_prepare(cycle)

        def run():
            try:
                self.supervisor.run_forever(stop_event=stop, poll_seconds=0.01)
            except BaseException as error:
                errors.append(error)

        self.broker.prepare_worktree = prepare
        controller = threading.Thread(target=run, name="test-stopping-controller", daemon=True)

        def cleanup():
            stop.set()
            release_preparation.set()
            self.executor.release_all()
            controller.join(timeout=5)

        self.addCleanup(cleanup)
        controller.start()
        self.assertTrue(preparing.wait(5))
        stop.set()
        release_preparation.set()
        controller.join(timeout=5)
        self.assertFalse(controller.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(self.executor.calls, [], "Stopping during worktree preparation admitted a model call")
        self.assertEqual(self.autonomy.list_attempts(), [])
        self.assertEqual(self.autonomy.service_snapshot()["status"], "stopped")


class ParallelReservationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.tasks = Store(self.root / "state.db").initialize()
        self.autonomy = AutonomyStore(self.tasks.path).initialize()
        self.policy = {"max_daily_seconds": 20, "max_daily_attempts": 2, "max_concurrency": 4}
        self.executor = BlockingExecutor()
        self.pipeline = Pipeline(self.root, self.tasks, self.autonomy, self.policy,
                                 broker=ParallelBroker(self.root, self.executor), executor=self.executor)
        self.addCleanup(self.executor.release_all)

    def cycle(self, task_id):
        cycle = self.autonomy.create_cycle(task_id, "engineer")
        worktree = self.root / task_id
        worktree.mkdir()
        self.executor.worktrees[str(worktree)] = task_id
        return self.autonomy.update_cycle(cycle["id"], phase="authoring", worktree=str(worktree))

    def test_simultaneous_calls_cannot_exceed_shared_daily_runtime_or_attempt_cap(self):
        cycles = [self.cycle("T%s" % index) for index in range(4)]
        barrier = threading.Barrier(5)

        def invoke(cycle):
            barrier.wait(timeout=5)
            return self.pipeline._job(cycle, "author:0", "Scoped task", 10, "workspace-write")

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(invoke, cycle) for cycle in cycles]
            barrier.wait(timeout=5)
            try:
                self.assertTrue(self.executor.wait_for_calls(2))
                budget = self.autonomy.get_budget(self.policy)
                self.assertEqual(budget["attempts"], 2)
                self.assertEqual(budget["used_seconds"], 20)
                self.assertEqual(budget["reserved_seconds"], 20)
                self.assertEqual(budget["remaining_seconds"], 0)
            finally:
                self.executor.release_all()
            completed = denied = 0
            for future in futures:
                try:
                    self.assertEqual(future.result(timeout=5)["status"], "completed")
                    completed += 1
                except BudgetExceeded:
                    denied += 1
        self.assertEqual((completed, denied), (2, 2))
        self.assertEqual(len(self.executor.calls), 2)
        self.assertEqual(len(self.autonomy.list_attempts()), 2)

    def test_simultaneous_duplicate_stage_calls_execute_only_once(self):
        cycle = self.cycle("EXACT")
        barrier = threading.Barrier(3)

        def invoke():
            barrier.wait(timeout=5)
            return self.pipeline._job(cycle, "author:0", "Same exact stage", 10, "workspace-write")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke) for _ in range(2)]
            barrier.wait(timeout=5)
            try:
                self.assertTrue(self.executor.wait_for_calls(1))
                self.assertEqual(len(self.autonomy.list_attempts()), 1)
            finally:
                self.executor.release_all()
            completed = duplicate = 0
            for future in futures:
                try:
                    self.assertEqual(future.result(timeout=5)["status"], "completed")
                    completed += 1
                except (DuplicateAttempt, CapacityUnavailable):
                    duplicate += 1
        self.assertEqual((completed, duplicate), (1, 1))
        self.assertEqual(len(self.executor.calls), 1)
        self.assertEqual(len(self.autonomy.list_attempts()), 1)

    def test_capacity_denial_creates_no_attempt_and_does_not_spend_daily_budget(self):
        self.policy.update(max_concurrency=2, max_daily_seconds=1000, max_daily_attempts=20)
        self.pipeline.policy.update(self.policy)
        cycles = [self.cycle("LIMIT%s" % index) for index in range(4)]
        barrier = threading.Barrier(5)
        condition = threading.Condition()
        denied = []

        def invoke(cycle):
            barrier.wait(timeout=5)
            try:
                return self.pipeline._job(cycle, "author:0", "Capacity check", 10, "workspace-write")
            except CapacityUnavailable:
                with condition:
                    denied.append(cycle["id"])
                    condition.notify_all()
                raise

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(invoke, cycle) for cycle in cycles]
            barrier.wait(timeout=5)
            try:
                self.assertTrue(self.executor.wait_for_calls(2))
                with condition:
                    self.assertTrue(condition.wait_for(lambda: len(denied) == 2, timeout=5))
                budget = self.autonomy.get_budget(self.policy)
                self.assertEqual(budget["attempts"], 2)
                self.assertEqual(budget["reserved_seconds"], 20)
                self.assertEqual(len(self.executor.calls), 2)
            finally:
                self.executor.release_all()
            completed = capacity_limited = 0
            for future in futures:
                try:
                    self.assertEqual(future.result(timeout=5)["status"], "completed")
                    completed += 1
                except CapacityUnavailable:
                    capacity_limited += 1
        self.assertEqual((completed, capacity_limited), (2, 2))
        self.assertEqual(len(self.autonomy.list_attempts()), 2)

if __name__ == "__main__":
    unittest.main()
