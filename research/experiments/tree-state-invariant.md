# Tree state invariant experiment

## Scope and source

This reproduces the structural recursion probe from public PR 53, candidate
source revision `df15a532890cfb037f1df54508d4de92f0c613a4`, on current base
revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`. The candidate model and
proof branch were inspected at that source revision. The reproduction retains
the theorem and false control, the locally existing tactic paths, and the
current `Colony.lean` imports. No commit was created; results below apply to
the uncommitted working tree after these changes:

| File | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `4fe5d644e0ecd00072d58df948e96d6bbe8c9195ef99fa072c7281b965cd09a4` |
| `lean/Colony.lean` | `2a2e48104b62379c4d05e3ac3e9f0c5ed28492abd24e88bed2f7190b38677910` |
| `lean/Colony/Procedures/TreeState.lean` | `1c74d0c8c7aad09bb6518f148e3f8f8fd59d3d40a7ad5a3c9ea1f27f27783ad4` |
| `lean/Colony/Examples/TreeStateInvariant.lean` | `5df664deb93338f8e97a02c51f4c7423e140fc5169dd7afa66825318fa5cfe5d` |

The binary tree has an empty constructor and nodes with a command and two
subtrees. `noop` preserves both counters; `tick n` increments both. Execution
threads state through the root, left subtree, then right subtree. The theorem
statement remains:

```lean
theorem execute_preserves_tree_state_invariant
    (tree : CommandTree) (state : TreeState)
    (h : state.leftCount = state.rightCount) :
    (execute tree state).leftCount = (execute tree state).rightCount
```

The new tactic branch requires exactly one local whose type reduces to
`CommandTree`. It generalizes other non-propositional locals, snapshots tactic
state, and restores that snapshot on failure. For each node, it applies the
right and left induction hypotheses at the threaded intermediate states, then
splits the command; simplification and `omega` close the resulting branches.
The branch does not invoke `colony` recursively. The negative offset control is
guarded by `fail_if_success colony`. A concrete multi-node execution and an
unequal-state counterexample provide non-vacuity checks.

## Commands and results

Lean 4.35.0 (toolchain commit `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`,
Release), commands run from `lean/`:

- `lake build Colony` — passed, 15 jobs. This elaborated the invariant with
  `by colony`, its guarded false control, the concrete tree examples, and
  existing examples imported by `Colony`.
- `printf 'import Colony.Examples.TreeStateInvariant\n#print axioms Colony.Examples.execute_preserves_tree_state_invariant\n' | lake env lean --stdin`
  — passed; Lean reported `[propext]` for the theorem.
- `git diff --check` — passed.

The initial build failed on the added rollback regression example because its
attempted fallback used a bridge theorem defined only after the example import
in `Colony.lean`. That regression was removed; no change to the existing theorem
or import order was needed. Thus restoration is implemented by the saved
candidate snapshot and catch path, but this run does not claim an independent
focused rollback regression passed. No other candidate-shape experiment was
run in this reproduction.

## Assurance limits

Successful elaboration and the build establish Lean kernel acceptance of the
ordinary proof term in this configured Lean environment. The axiom report
contains only standard `propext`; the change adds no `sorry`, `admit`, or
axioms. The false control's guarded tactic attempt fails during compilation.
No exported replay, independent-kernel check, benchmark score, or correspondence
to Cardano execution was tested or established.
