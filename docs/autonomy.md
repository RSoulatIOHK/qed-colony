# Continuous colony operation

The persistent supervisor dispatches bounded work, resumes durable pipeline
phases, and keeps a real service heartbeat for the Observatory. The research and
implementation agents develop the prover; the released tactic still runs
locally without a model call.

Run one durable controller step or keep the loop in the foreground:

```sh
python3 -m colony supervise --once
python3 -m colony supervise --port 7331
```

On macOS, manage the persistent user LaunchAgent with:

```sh
python3 -m colony service install --port 7331
python3 -m colony service start
python3 -m colony service status
python3 -m colony service stop
```

The persistent process also serves the local Observatory. A user LaunchAgent
runs within the logged-in user's environment; it needs the machine awake, the
required network services reachable, and a valid Codex CLI login. Stopping the
service preserves its durable queue and pipeline state.

## Acceptance contract

A cycle starts from an explicitly scoped task and its acceptance criteria. Its
implementation goes through authoring, controller publication, independent
review, CI, and the configured merge gate. A task is complete only after the
pipeline verifies its actual outcome. A model's exit status, a PR URL, or a
green task card is not a proof certificate.

Workers produce local artifacts. The controller owns GitHub publication and
merge authority. Changes to evaluation rules, challenge statements, authority,
or resource policy require separate governance review; they cannot improve the
score of the same implementation. Existing proof assurance requirements apply
throughout this loop.

## Durable state and restart behavior

SQLite stores one cycle per task ID. Cycle context preserves the branch,
revision, PR identity, review evidence, and current phase before the next
controller action. Reopening the database does not create a second cycle for
the same task. The pipeline reconciles remote PR and CI state before repeating
publication or merge actions.

The supervisor takes an exclusive `flock` beside its database before dispatching
anything. The operating system releases this lock when the process exits. The
lock file is deliberately not deleted: unlinking a live lock would permit two
controllers to acquire different inodes for the same database. The initial
controller dispatches one cycle at a time.

Each model invocation first reserves an attempt with a unique stage label,
such as `author:1` or `review:<revision>`. A restart marks an unfinished attempt
`interrupted` and its cycle `needs_review`, retaining its artifacts, PR identity,
and entire runtime reservation. It does not silently repeat uncertain work.
Ordinary phases without an unfinished model attempt resume normally, including
publication reconciliation and CI polling. Intentional retries need a new
explicit stage label. Orphan worker cleanup belongs to the execution runner;
the SQLite lease or supervisor lock alone cannot terminate an OS process.

An empty queue means healthy waiting. The supervisor checks the bounded planner
again on later polls. Budget exhaustion means waiting for a reset; it never
marks unfinished tasks complete. A failed or interrupted cycle remains visible
for review rather than becoming an infinite retry loop.

## Budget policy

The `autonomy` object in `colony.json` controls the unattended service. Its
operational limits include:

```json
{
  "enabled": true,
  "max_daily_seconds": 14400,
  "max_daily_attempts": 72,
  "timezone": "Europe/Paris",
  "poll_seconds": 30
}
```

The current experimental allocation is four worker-hours and 72 attempts per Paris calendar day, not a monetary price. Existing usage is retained when limits change. The
selected model, reasoning effort, tokens, and measured elapsed time should be
recorded with the attempt. Model selection policy can use cheaper models for
routine work and stronger models for difficult research or review while sharing
the same runtime and attempt caps.

Reservation uses a SQLite write transaction: simultaneous launch requests cannot
both spend the same remaining allocation. Before launch, the entire worker
timeout must fit. A known completed or stopped invocation charges its measured
elapsed time, releasing any unused reservation. If termination is uncertain, the
full reservation remains charged. Fast failures still consume an attempt so a
broken worker cannot repeatedly launch for free.

Accounting assigns an invocation to its launch date in the configured timezone.
An invocation crossing midnight retains its original day's allocation; a new
date gets a fresh allocation. Reset times follow local midnight, including
daylight saving changes. Runtime and attempt caps limit launches, not subscription
token quotas or API spending. Execution deadlines and process termination are
enforced by the runner separately.

Budget exhaustion prevents new planning and task dispatch. Existing cycles can
still poll CI or reconcile a PR without calling a model. Every subsequent model
call must obtain its own reservation and can wait for the next reset.

## Service state and API

`AutonomyStore.service_snapshot()` returns:

```text
status, pid, active_cycle, message, heartbeat,
heartbeat_age_seconds, stale
```

Before the first start, status is `stopped`, heartbeat is null, and stale is true.
An active process refreshes its heartbeat during long model calls as well as
between dispatches. A heartbeat older than 120 seconds is stale. A snapshot is
evidence of the last observed state, not proof that a remote process is alive.
Static Observatory exports remain explicitly static.

`get_budget(policy)` returns the local date, timezone, reset timestamp, used and
reserved seconds, remaining seconds, attempt count, remaining attempts, limits,
and an `exhausted` flag. Cycles contain fixed `id`, `task_id`, `role`, `phase`,
`created_at`, and `updated_at` fields plus the pipeline's context. Pipeline
context is private operational state: the public Observatory must select safe
fields instead of exporting local worktree paths or private worker logs.

Public Python interfaces are:

```text
AutonomyStore(db_path).initialize()
create_cycle(task_id, role) -> cycle
get_cycle(cycle_id) -> cycle or None
next_cycle() -> oldest nonterminal cycle or None
list_cycles() -> cycles
update_cycle(cycle_id, phase=None, **context) -> cycle
reserve_attempt(cycle_id, stage, timeout_seconds, policy) -> attempt ID
finish_attempt(attempt_id, elapsed_seconds, usage=None, status="completed")
list_attempts(cycle_id=None) -> attempts
get_budget(policy) -> budget
reconcile_interrupted() -> interrupted attempts
set_service(status, pid, active_cycle=None, message="")
service_snapshot(policy=None) -> service

Supervisor(root, db_path, policy, pipeline=None, task_store=None)
startup() -> supervisor
tick() -> current service result
run_forever(stop_event=None, poll_seconds=None)
acquire_lock() -> supervisor
release_lock()
```

The injected pipeline exposes `advance(cycle)` and `plan()`. It owns durable
phase transitions and must reserve every model call. `BudgetExceeded` keeps the
cycle at its current phase. `DuplicateAttempt` prevents accidental reuse of an
already executed stage. Unexpected controller errors put the active cycle into
`needs_review` instead of repeatedly running a potentially mutating operation.

Run focused state and restart tests with:

```sh
python3 -m unittest discover -s tests -p 'test_autonomy_store.py' -v
python3 -m unittest discover -s tests -p 'test_supervisor.py' -v
```

This remains a local controller, not a hostile-worker isolation boundary. The
owner of its files can change its policy, database, or runtime. The evidence and
review gates must describe the assurance actually achieved; unattended operation
does not strengthen a proof claim by itself.
