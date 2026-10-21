# AUTO-7e7cc06199: bounded `Except` branching

## Scope and acceptance

Add deterministic local branching for at most the eligible `Except` candidates
present in the local context, trying them in context order. Every candidate is
bounded to its two constructors; if any branch stays open or fails, restore the
tactic state and try the next candidate. Demonstrate a two-counter result
transition, unchanged failure state, restoration after an irrelevant candidate,
and rejection of a nearby false target.

## Implementation

`Colony.Tactic` now scans local declarations for `Except` types and snapshots
the tactic state before trying each candidate. `exceptPortfolio` cases the
candidate and requires all branches to close by deterministic simplification,
Presburger arithmetic, or closed decision. `ResultFlow.lean` defines
`applyResult`: `.ok amount` adds `amount` to both counters and `.error _`
returns the input pair. The positive theorem statement and assumptions are:

```lean
(state : Nat × Nat) (result : Except String Nat)
(h : state.1 = state.2) :
(applyResult state result).1 = (applyResult state result).2
```

The example also proves failure leaves state unchanged, tests an irrelevant
first `Except` candidate followed by the useful candidate, and guards a false
target with `fail_if_success`.

## Evidence

- Base/source revision before edits: `b9a946a3953fc55e7da19c0fd5d3f66a3193dd39`.
- Exact successful command: `cd lean && lake build Colony`.
- Result: exit code 0; `Colony.Tactic`, Boolean, Option, ListState, ResultFlow,
  and the aggregate `Colony` target built. Existing unused-variable linter
  warnings remain in the preexisting examples and the intentionally irrelevant
  candidate/example binders.
- Failed attempt: `cd lean && lake env lean Colony/Examples/ResultFlow.lean`
  exited with unknown module prefix `Colony` because the library had not yet
  been built into `.lake/build`.
- Failed proof experiment: the first positive result theorem asked for
  preservation of a natural subtraction difference after success. The current
  branch portfolio did not close its arithmetic obligations. It was replaced
  with the stated equal-counter invariant, where both constructor branches
  simplify and close. An initial build also exposed that the transition needed
  to be a simp lemma; marking `applyResult` with `@[simp]` resolved that.

## Assurance and limits

The result demonstrates Lean elaborator kernel acceptance for this local
Lean 4.35.0 build. No exported replay, independent-kernel acceptance, or
correspondence to Cardano execution was checked. This is a small deterministic
portfolio extension, not a completeness or performance claim.
