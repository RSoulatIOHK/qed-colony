# AUTO-3b186ab3a7: bounded splitting on `ListCommand`

## Scope and acceptance criteria

Add a deterministic fallback to `by colony` that selects at most one eligible
`Colony.Procedure.ListCommand` parameter, splits its constructors, and restores
the tactic state if the candidate fails. Prove the unchanged one-step invariant
under the unchanged assumption `state.balance = state.recorded`; reject an
intentionally false one-step equality. Existing Boolean branching and list-state
examples must elaborate.

## Changes

`Colony.Tactic` scans the local context in declaration order. At the first
non-implementation-detail local whose weak-head-normalized type is
`Colony.Procedure.ListCommand`, it saves tactic state, performs `cases`, and
tries `simp_all [Colony.Procedure.step] <;> omega` on every generated branch.
If the candidate fails, it restores the saved state and ends this fallback
without trying another command parameter. The new example proves

```lean
(step state command).balance = (step state command).recorded
```

from the original equality assumption using `by colony`. A neighboring
`fail_if_success` example checks that adding `1` to the recorded result is not
proved. `ListCommand`, `step`, and the theorem assumptions and conclusion are
unchanged.

## Failed approaches

- Splitting followed only by the existing arithmetic portfolio failed: `step`
  remained opaque in the resulting branches. The first `lake build Colony`
  attempt rejected `colony` at the one-step theorem.
- Running `simp_all [Colony.Procedure.step]` as an independent tactic before
  the arithmetic portfolio still did not close the branch in the second build
  attempt. The branch solver was changed to the combined
  `solve | simp_all [...] <;> omega` sequence, which closed both constructors.

## Lean check and assurance

- Exact command: `lake build Colony` (run from the `lean/` project directory).
- Toolchain: `leanprover/lean4:v4.35.0` as specified in `lean/lean-toolchain`.
- Result: success. Lake reported successful builds for
  `Colony.Procedures.ListState`, `Colony.Tactic`,
  `Colony.Examples.BooleanBranching`, `Colony.Examples.ListStateInvariant`,
  and `Colony.Seeds`. `ListStateInvariant` emitted only unused-variable
  warnings for the variables in the intentionally false check. Its
  `fail_if_success` check passed, as did the existing Boolean branching and
  list-state invariant examples.
- Assurance: Lean elaborator kernel acceptance for this build. This is not a
  claim of exported replay, independent-kernel acceptance, or correspondence
  to Cardano execution. No performance or benchmark superiority is claimed.
