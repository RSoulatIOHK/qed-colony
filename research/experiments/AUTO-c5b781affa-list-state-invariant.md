# AUTO-c5b781affa: list-state invariant across command sequences

## Scope and source

Base source revision: `52cb5e8280834af4cedd5d13a32512d7bb1e0c63`.
The experiment was performed as an uncommitted working-tree change based on that revision. The Lean project pins `leanprover/lean4:v4.35.0` in `lean/lean-toolchain`.

The procedure is `Colony.Procedure.process` in `lean/Colony/Procedures/ListState.lean`. Its commands either add the same amount to both `balance` and `recorded`, or leave the state unchanged.

## Exact theorem statement

```lean
theorem process_preserves_list_state_invariant
    (commands : List ListCommand) (state : ListState)
    (h : state.balance = state.recorded) :
    (process commands state).balance = (process commands state).recorded
```

The statement quantifies over every command list. The procedure, initial-state assumption, and conclusion are unchanged in the example. The theorem is proved by explicit induction after a recorded attempt with the unchanged `colony` tactic.

## Tactic attempts and negative control

Attempting `colony` directly on the theorem failed with:

```text
error: Colony/Examples/ListStateInvariant.lean:13:2: colony: the initial proof portfolio could not close this goal
```

That direct attempt was made in an initial `lake build Colony`, which exited unsuccessfully because the theorem ended in `by colony`. In the example source, `fail_if_success` reruns this same tactic on the exact theorem target and confirms failure; the theorem then closes by structural induction and `omega`.

The negative control asks `colony` to prove the invalid proposition
```lean
(process ([] : List ListCommand) ⟨0, 0⟩).balance =
  (process ([] : List ListCommand) ⟨0, 0⟩).recorded + 1
```
`fail_if_success` confirms that `colony` does not close it. The negation is independently established by `decide`.

## Commands and results

Commands were run from the `lean/` project directory:

```sh
lake build Colony
```

First run, while the target was directly `by colony`:

```text
✖ Building Colony.Examples.ListStateInvariant
error: ... colony: the initial proof portfolio could not close this goal
error: build failed
```

Second run, after recording the failed tactic attempt and supplying the explicit induction proof:

```text
✔ Built Colony.Procedures.ListState
✔ Built Colony.Tactic
✔ Built Colony.Examples.BooleanBranching
✔ Built Colony.Examples.ListStateInvariant
✔ Built Colony.Seeds
✔ Built Colony
Build completed successfully (8 jobs).
```

The first explicit induction script also failed once: it simplified the recursive call before applying the induction hypothesis, leaving `omega` an unrelated recursive equality goal. Applying the induction hypothesis first, then splitting the command and simplifying `step`, fixed that proof. The failed script was not retained.

## Assurance and limits

Lean v4.35.0 elaborated the example and checked its ordinary proof terms, including the explicit induction theorem and negative control. This is **Lean elaborator kernel acceptance** only. No exported replay, independent-kernel check, or correspondence to Cardano execution is claimed. The model is a small synthetic state procedure.
