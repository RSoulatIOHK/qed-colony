# AUTO-c85777844a: Array state invariant probe

## Scope and acceptance

Extend `colony` structural induction candidate selection to recognize an array
local when exactly one array candidate is in the local context. Add an array
update procedure, a fixed invariant theorem proved with exactly `by colony`,
and a deliberately false array goal that remains unsolved. No theorem-specific
tactic dispatch or helper proof was added.

## Changes

- `lean/Colony/Tactic.lean`: added generic array induction using the unique
  array-local candidate and generalized non-proposition locals.
- `lean/Colony/Examples/ArrayStateInvariant.lean`: added a `setIfInBounds`
  update, the size invariant, and a false size claim guarded by
  `fail_if_success`.
- `lean/Colony.lean`: imported the example.

## Reproduction and observed results

Source revision before these working-tree changes: `1f3d4ae4021907c8f15df570c46f506e16f5ca2d`.

Commands run from the repository root:

```sh
cd lean && lake build Colony
cd lean && lake env lean /tmp/array_axioms.lean
git diff --check
```

`lake build Colony` completed successfully (exit 0); this elaborates the
positive `by colony` theorem and checks the negative `fail_if_success` case.
The first establishes
`(updateArrayState state updated value).size = state.size`. The false claim
`(updateArrayState state updated value).size = state.size + 1` was not solved
by `colony`; otherwise `fail_if_success` would have failed the build.
`git diff --check` completed successfully.

The temporary `/tmp/array_axioms.lean` contained only:

```lean
import Colony.Examples.ArrayStateInvariant
#print axioms Colony.Examples.updateArrayState_preserves_size
```

Lean reported:

```text
'Colony.Examples.updateArrayState_preserves_size' depends on axioms: [propext]
```

Assurance: Lean 4.35.0 elaboration and kernel acceptance within the local
Lake build. This is not exported replay, independent-kernel validation, or a
claim about Cardano execution. No `sorry`, `admit`, or project-added axiom was
used; the reported `propext` dependency is Lean's standard propositional
extensionality axiom.

## Failed attempts

1. An initial other-slot invariant for `getElem?` after `setIfInBounds` failed
   under `by colony`: `simp_all` does not apply the relevant `grind`-tagged
   array lookup lemma. That theorem was removed rather than weakening the
   tactic with theorem-specific dispatch.
2. A first size-invariant attempt also failed because the simplifier did not
   unfold the named update procedure. Marking its definition `[simp]` made
   the fixed size invariant close and retained the generic tactic search.

## Limitation

The example confirms the array update invariant and exercises the tactic
integration, but it does not establish that this particular theorem reached
the new induction branch: the earlier generic simplification portfolio may
close it first. The candidate-selection branch is implemented, while a future
probe should choose an invariant that demonstrably requires array induction.
