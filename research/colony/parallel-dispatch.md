# Parallel autonomous dispatch

## Task and acceptance criteria

Replace the unattended controller's serial model dispatcher with a bounded
parallel dispatcher. The owner authorized up to four concurrent workers; the
existing eight aggregate worker-hours and 144 attempts per Paris day remain.

- Demonstrate overlapping independent model jobs, with no more than four calls
  in flight and no two stages executing for the same cycle at once.
- Admit ready work into free slots while other jobs run; allow a bounded planner
  to replenish independent work without duplicate planners.
- Keep worktree preparation, publication, review handoff, CI and merge serialized.
  An author's own review must await its completed and published candidate.
- Keep transactional shared budget reservations and conservative interrupted-call
  accounting. Capacity contention must not fabricate a started model attempt.
- Stop admission and drain bounded jobs before releasing the controller singleton.
  Preserve durable stage identities and existing restart reconciliation.
- Show actual active worker heartbeats and reserved/running calls separately in
  the Observatory. Never infer active workers from the roster or configured cap.
- Publish the change as a separate governance PR, independently review it, pass
  appropriate checks, and explicitly install the reviewed runtime. Verify real
  overlapping worker calls after activation before claiming live parallelism.

## Initial observation

The earlier dispatcher called each model executor synchronously. Its unattended
policy admitted one worker; the separate legacy worker command's limit of four
did not provide parallel autonomous dispatch. Increasing the daily budget or
changing only the slot guard could not fix that scheduling behavior.

## Evidence

The initial Python suite passed 266 tests, JavaScript syntax passed, and the
Lean evaluator preserved eight positive proofs and the rejected invalid
shared-payment claim. This evaluator result is Lean elaboration/kernel evidence;
it does not establish exported replay or independent-kernel acceptance.

The first parallel test fixture incorrectly assumed that only its author/review
calls could occupy spare lanes; it failed when the new planner ran alongside
them. The fixture now identifies exact task/stage calls and separately checks
single-planner refill while an original author remains blocked. These tests use
controlled executors, never provider calls. Review also identified queued
planner/triage paths that needed explicit preparation before submission, and
controller-only network resumptions that must progress even with all lanes busy.
Regression cases cover these boundaries.

Implementation, regression results, and the final activation observation are
recorded in the public governance PR. This change concerns colony throughput;
it does not establish new Lean proof or Cardano correspondence assurance.
