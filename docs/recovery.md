# Recovery of parked pull requests

Scope: give stopped work an explicit owner and one bounded path forward without
weakening its original acceptance criteria. Recovery diagnoses a particular
parked cycle; periodic operations audits remain responsible for broader process
improvements. The controller performs publication and integration. Recovery
workers receive no additional authority.

## Detection and ownership

Every controller tick scans parked cycles before cycle selection and the model
budget gate. It records a recovery case on the original cycle, including a
reason, owner, next action, and fixed UTC next-action deadline. Merely creating
that case or assigning an owner does not call an LLM or reserve an attempt.
Dispatching triage, authorship, or review still requires the same daily runtime
and attempt caps as every other model job. A queued case is recorded work, not
an assertion that a model is currently running.

An unsupported original execution role receives a controller scope review
instead of another model call that cannot implement its acceptance. Planning
decisions are saved before their handoff; restart can apply that saved decision
without purchasing another diagnosis.

Active cycles advance in round-robin order, allowing another cycle to progress
while one waits for CI. This changes scheduling fairness, not review, proof,
publication, or budget requirements.

The root cycle carries these public fields when recorded:

| Field | Meaning |
| --- | --- |
| `recovery_owner` | Current accountable owner: controller, blocker-triage, or repair-author |
| `recovery_status` | Recorded case stage from the table below |
| `recovery_reason` | Why the source cycle needs attention |
| `recovery_next_action` | Concrete next step |
| `recovery_next_action_deadline` | Fixed UTC deadline; not moved forward by each scan |
| `recovery_diagnosis` | Recorded triage conclusion |
| `recovery_triage_cycle_id` | Associated read-only triage cycle |
| `recovery_repair_cycle_id` | Associated fresh repair cycle, if any |
| `recovery_repair_task_id` | Repair assignment retaining the original criteria |
| `source_pr_url`, `source_head_sha` | Source candidate identity, when available |

Child cycles carry `recovery_kind` (`triage` or `repair`) and `recovery_root_id`.
The Observatory derives links only to recorded tasks, displays the owner and
next action on Kanban cards and task details, and lists cases on the overview.
Snapshots remain timestamped evidence rather than confirmation of current
activity.

## Bounded diagnosis and repair

A case permits at most one read-only model triage attempt of 180 seconds. The
triager receives the original task, candidate/review evidence, and failure
context, then returns structured operational planning. The controller validates
that result against the existing roles and permissions. A diagnosis cannot
change policy, theorem statements, assumptions, bounds, or acceptance criteria.

A validated diagnosis may queue one fresh repair task/cycle directly; an
operations audit PR does not have to merge first. The repair copies the original
specification and acceptance criteria unchanged and gets at most one author
attempt and one independent reviewer. Its new public PR must pass the normal
required CI and exact-current-head review gates. A successful process exit,
research proposal, green CI alone, or a merge without the required evidence does
not establish acceptance.

The repair author is capped at 480 seconds and the reviewer at 240 seconds,
or their smaller configured timeout. A repair receives no automatic author or
reviewer retry. The original cycle retains its previous failed attempts and
charges; recovery never resets that ledger.

If triage fails, the repair fails or is rejected, or the task requires an unknown
or mismatched execution profile, the case escalates to the controller. Recovery
does not recursively recover its own triage/repair cycles or create an unbounded
spawn chain. Proposals for new roles remain proposals until a separate,
authorized governance change defines their execution scope.

## States and completion

| Status | Meaning |
| --- | --- |
| `triage_queued` | A diagnosis is assigned and awaits dispatch/budget |
| `triaging` | The recorded triage attempt is underway |
| `repair_queued` | One validated repair is assigned and awaits dispatch/budget |
| `repair_in_progress` | The repair cycle is running through its normal gates |
| `repair_merged` | Repair merged; source acceptance/closure reconciliation remains |
| `awaiting_controller_integration` | Reviewed governance candidate is at its controller handoff |
| `controller_scope_review` | Controller must settle a missing or mismatched execution scope |
| `escalated` | The bounded path stopped and needs controller action |
| `resolved` | The controller recorded actual acceptance and required reconciliation |

An already approved SRE governance candidate waiting for controller integration
is not an automatic repair target. Recovery records controller ownership and
keeps the integration handoff visible; it never automatically deploys or expands
its own authority.

The original task and PR remain parked while the repair runs. A merged repair
must not itself mark the original task done or claim the case resolved. Source
PR closure, if required, is a separate controller reconciliation step after
repair acceptance and remote verification. Until that evidence is recorded, the
case remains open and the Observatory keeps its intermediate status visible.

The controller verifies the replacement's merged state, exact approved head,
required CI, and unchanged original specification before closing the source as
superseded. A controller-authored closure marker makes interrupted closure
reconcilable. It then atomically records original-task completion and releases
its dependents. The original rejected head is never reported as merged or
approved. GitHub does not provide an atomic head-conditioned close: the broker
checks the source immediately before and after closure. A concurrent head
change requires controller attention and prevents original-task completion.

The GitHub Project can mark a closed source as Done when fresh local evidence
records its verified replacement and resolved recovery. GitHub-only sync keeps
an unmerged closed source Blocked because it cannot establish that replacement
acceptance from the original PR alone.
