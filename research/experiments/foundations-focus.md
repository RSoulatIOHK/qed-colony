# Foundations focus: operator-directed task scope

## Scope and acceptance before implementation

This change proposes three bounded jobs in `tasks/foundations-focus.json`: repair
generic arithmetic normalization, measure existing basic mathematics coverage,
and prevent duplicate planner objectives. It changes no controller code, worker
permissions, benchmark input, evaluator, theorem statement, or operational state.
The controller decides when to admit these jobs and publishes their reviewed
artifacts through the existing workflow. Adding this file does not activate them.

The implementation jobs must preserve the original declarations and close every
claimed success with exactly `by colony`. A manual proof, an outside helper
proved specifically for a target, or a changed assumption is not a tactic win.
Report Lean elaborator/kernel acceptance and actual axiom dependencies; do not
claim independent-kernel replay or Cardano correspondence.

## Observed problem

The inspected backlog contained older state-transition examples using `Except`
and `Sum` in CI (PRs 47 and 52), alongside new arithmetic work. The planner had
already generated generic commutative rewriting (PR60 / AUTO-3f0db8ced4) and
ordered-product monotonicity (PR61 / AUTO-700000bc74), then admitted duplicate
objectives AUTO-f0c580b6be and AUTO-abd0a5c138. A filtering investigation likewise
appeared as both PR65 / AUTO-4c5c3726b7 and ready AUTO-cd69a3c234. These are
observations of that inspection, not a claim about their present status.

The planner prompt asks for progress toward complex program verification and
reads existing experiments. Its duplicate prohibition is prose. Active-task
context contains titles, roles and statuses, while proposal admission assigns
fresh IDs without a deterministic objective or integration-surface check.
Additionally, its recent-history slice uses a priority-ordered task snapshot,
rather than selecting tasks by chronology. Persisted task descriptions and
acceptance criteria continue to bind already admitted workers.

The historical report at source revision `2bd489` recorded 9/12 successful
`by colony` cases. Its three failures were natural addition commutativity,
right commutativity, and multiplication monotonicity. This is historical
evidence, not a latest-score claim. The controller's separate Lean diagnostic
identified reducible type aliases as an arithmetic backend obstacle using the
unchanged upstream statements. No command output, timing, or new successful
result from that diagnostic is invented here. MATH001 must reproduce and record
the behavior before changing the tactic.

## Focus and unsuccessful approaches

Repeated example construction and prompt-only duplicate avoidance have not
established coverage of basic arithmetic. Additional state-machine scaffolds
are unnecessary for these next jobs. The focus is generic Nat/Int reasoning,
ordinary natural/list laws, reproducible failures, and measured improvement on
unchanged goals. This does not constrain the eventual tactic architecture.

MATH001 owns normalization changes and its distinct alias examples. MATH002
measures the currently reviewed implementation in a separate example module and
research artifact; it does not depend on MATH001 or alter the tactic. The SRE job
owns planner admission changes in a separate governance PR, within the existing
SRE file allowlist. It must preserve independent parallel work while preventing
duplicate objectives and conflicting implementation ownership.

This queue declaration does not cancel, rewrite, or mark existing work complete.
At a bounded controller handoff, the controller should reconcile duplicate
objectives and preserve their artifacts before admitting replacement work. No
worker may raise its authority, change caps, publish, merge, or deploy itself.

## Validation

Validate the task JSON with the existing Store seeding format, check role and
path restrictions against the current broker, and inspect the diff for private
paths or fabricated results. No Lean implementation or benchmark result is
changed by this queue-only proposal. Each eventual worker must record actual
commands, source revision, complete positive/negative outcomes, and failed
experiments in its own artifact.

## Subsequent measured result

The strict persistent runner completed the same 56-row protocol at
`3b11188d52ad5ff8c1f1885508b44c1d6e584f66` on 21 October 2026 at 15:17:17 UTC.
The [complete report](../../benchmarks/results/blaster-nng4-3b11188d.json)
records Colony 12/12, simp_all 7/12, omega 1/12 and grind 11/12. Every strategy
passed its non-vacuity and invalid controls. The original fixed statements,
exact `by colony` bodies and evaluator suite are unchanged. This closes the
three initial failures; it does not establish broad mathematics coverage or a
matched Lean Blaster comparison. The next jobs therefore test broader ordinary
mathematics and fresh alias forms rather than repeating those solved targets.
