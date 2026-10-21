# AUTO-000fab7040: bounded `Except` split on a state transition

## Scope and target

This experiment adds one isolated transition example and one narrowly scoped
`Except` fallback in `Colony.Tactic`. The positive target is unchanged by the
tactic and is exactly:

```lean
theorem transition_advances (input : Input) (state : Nat) :
    transition state input > state
```

Here `Input := Except Failure Nat`, where `Failure` has `rejected` and
`unavailable` constructors. The unchanged transition adds two on `.error` and
adds `value + 1` on `.ok value`. The bound is strict advancement (`> state`);
there are no extra assumptions.

The proof first runs `simp only [transition]` in the example. This exposes the
outer result match, and is example-level preprocessing, not a tactic-controlled
split. `colony` then selects one eligible local declaration whose weak-head
type is `Except`, attempts exactly one `cases` split, and runs the existing
arithmetic portfolio on each resulting branch. It saves and restores tactic
state if that attempt fails. It does not recurse into `Failure` or search
multiple eligible declarations in one attempt. `fail_if_success colony` around
the nearby stronger bound confirms that a failed attempt does not leave a
partial proof state.

The stronger claim `transition state input > state + 2` is refuted by the
concrete counterexample `input = .ok 0`, `state = 0`. The source also includes
an explicit failed-automation check for this false target.

## Reproducible evidence

- Base/source revision: `a04ebf6b026204270d88f26d813c95220e127284` (the working
  changes were uncommitted at check time).
- SHA-256 of `lean/Colony/Tactic.lean`:
  `51575ec583cf0bae446533cfb761a4c05df24c20788f8a8dd222b96fad6771b6`.
- SHA-256 of `lean/Colony/Examples/ExceptStateTransition.lean`:
  `f2a997ed7e4286aa0b3d9c4e511f245ef895f7297f47299579dc91f7dbc065c3`.
- From `lean/`, `lake env lean Colony/Examples/ExceptStateTransition.lean`:
  exit 0, no diagnostics. `#print axioms` reports
  `[propext, Quot.sound]` for `transition_advances`.
- From `lean/`, `lake build Colony.Examples.ExceptStateTransition`: exit 0,
  `Build completed successfully (4 jobs)`.
- `git diff --check`: exit 0.

## Assurance and limits

The theorem's proof term was accepted by the Lean elaborator/kernel in this
toolchain. The reported axioms are Lean's standard `propext` and `Quot.sound`;
no custom axioms, `sorry`, or `admit` were introduced. This does not establish
exported replay, independent-kernel acceptance, or correspondence to Cardano
execution. Build success is corroborating command evidence, not a separate
proof certificate.
