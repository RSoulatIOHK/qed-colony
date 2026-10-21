# AUTO-7e87e900e8: bounded list procedure recursion

Historical experiment record: the theorem and bound claims below were superseded
by `AUTO-7e87e900e8-bounded-list-review-followup.md`. The umbrella import described
here exceeded the task scope and is removed by the correction recorded in
`AUTO-7e87e900e8-bounded-list-scope-correction.md`; use that report for current
source identity and check results.

## Scope and result

Base revision: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
Toolchain: `leanprover/lean4:v4.35.0` (`lean/lean-toolchain`).

The focused example `Colony.Examples.bounded_process_preserves_list_state_invariant`
keeps the statement and assumption of the existing arbitrary-list invariant:

```lean
(commands : List ListCommand) (state : ListState)
(h : state.balance = state.recorded) :
(process commands state).balance = (process commands state).recorded
```

It closes by `colony`. The tactic's list fallback considers a list only when
exactly one non-implementation-detail local has type `List ListCommand`. It
saves tactic state before trying one induction on that candidate, generalizes
non-proposition locals, simplifies the `process` and `step` equations, and
uses `omega`. If a branch needs a command split, it splits a command local
once in that branch and retries the simplifier/arithmetic solver. Failure
restores the saved state. The bound is on list candidates/induction attempts,
not a depth bound on the structural induction: Lean generates the ordinary
nil/cons proof obligations.

The neighboring intentionally false offset claim uses the concrete witness
`[ListCommand.record 1]` from state `⟨0, 0⟩`. Its negation closes by `decide`,
and `fail_if_success` confirms `colony` rejects the false positive equality.
The existing list-state example target also remains unchanged and builds.

## Checks and source identity

Commands were run from the `lean/` project directory:

```sh
lake build Colony
lake env lean <temporary axiom-query source>
git diff --check
```

`lake build Colony` exited 0 and completed all 11 build jobs, including
`Colony.Tactic`, both list-state examples, and `Colony`. Existing linter
warnings remain in option/list-state/accumulator examples. The axiom query
printed:

```text
'Colony.Examples.bounded_process_preserves_list_state_invariant' depends on axioms: [propext]
```

SHA-256 at the checked source state:

| File | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `fd132f0ef9c18d0ef072721720bfcdf34844c64a2d84eb327182393edae5f6d5` |
| `lean/Colony/Procedures/ListState.lean` | `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0` |
| `lean/Colony/Examples/BoundedListProcess.lean` | `ae57cc9fdaaee26522d47bd605feb09e071eeaf942d16ee774eb6216ee71f6c9` |
| `lean/Colony/Examples/ListStateInvariant.lean` | `10746c7bc8ee2ce9ba403c269c994b4baa47fe45cccae61bf64715a52b9762e8` |
| `lean/Colony.lean` | `cb59a4ead3920f830e636d2bef14350b99a64c8e644fb07cb1d648fad7496dff` |

Failed tool attempts and outcomes:

- Direct `lean Colony/Examples/ListStateInvariant.lean` used Lean 4.24.0,
  not the project toolchain, and failed with `unknown module prefix 'Colony'`.
  Lake's environment with the pinned Lean 4.35.0 resolved the modules.
- A follow-up `lake env lean --run` with empty stdin failed with
  `(interpreter) unknown declaration 'main'`; it was not a source failure.
  The axiom query was rerun as a temporary Lean source file and succeeded.

## Import and simplifier effects

`Colony.lean` now imports the focused example, making its declarations part of
the umbrella module's shared import surface. `Tactic.lean` already imported
`Std.Tactic`; this change adds only a comment describing the existing bound
and makes no global simp-set changes. The fallback explicitly simplifies
`Colony.Procedure.process` and `.step` together with `simp_all`, so any
simplification from those equations and the shared `Std.Tactic` environment
participates in the proof.

## Assurance and limits

The positive theorem has an ordinary Lean term accepted during Lean
elaboration/kernel checking; its reported axiom dependency is `propext`.
The false claim is rejected by the tactic and independently refuted by the
concrete computation. No exported replay, independent-kernel acceptance, or
correspondence to Cardano execution is established. This is a single local
experiment, not a performance benchmark.
