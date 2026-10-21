# Bounded tree-state invariant probe

## Scope and acceptance

This probe adds a binary command tree, a state transition that applies the
tree's total tick amount equally to two counters, and one `colony` induction
branch restricted to exactly one local of type `CommandTree`. The branch
generalizes non-propositional locals other than the tree, then uses only
`simp_all` over the tree execution/weight definitions followed by `omega`.
Candidate failure restores the saved tactic state. The example theorem
statement is proved with `by colony`; the false offset control is guarded by
`fail_if_success`.

## Source revision and commands

- Base source revision: `3a7c71e41ba1a29df363e8847fbe5a01e3a96bf8`.
- `lake build Colony` (from `lean/`): passed, 12 build jobs. Lean emitted
  existing linter warnings in `AccumulatorLength`, `ListStateInvariant`, and
  `OptionBranching`, plus unused binders in the false-control example.
- `git diff --check`: run after implementation; result recorded with the
  final worktree review.

## Failed candidate shape

An initial model threaded state through recursive execution of the left and
right subtrees. The fixed simplification-and-arithmetic branch could not use
the quantified induction hypotheses at those intermediate states, so that
candidate did not close. The model was changed to compute a recursive tree
weight and add that shared weight to both counters. An initial build also
exposed a missing direct import of `TreeState` in `Tactic.lean`; the import was
added before the passing build.

## Assurance and limits

Lean accepted the unchanged invariant theorem and the false control in the
compiled `Colony.Examples.TreeStateInvariant` module. Successful tactic
branches produce ordinary elaborated proof terms, which Lean's kernel checks.
This does not claim exported replay, acceptance by an independent kernel, or
correspondence to Cardano execution. The local Lean build is the only assurance
established by this experiment.
