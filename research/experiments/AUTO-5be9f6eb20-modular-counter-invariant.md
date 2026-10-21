# AUTO-5be9f6eb20: Modular counter invariant

## Frozen experiment

Base revision: `c0681623823204dc02c5a63460c1e69cc2e3a196` (Lean toolchain `leanprover/lean4:v4.35.0`). The transition is defined in `lean/Colony/Examples/ModularCounterInvariant.lean` as `step`: for `pc : Fin (n + 1)`, it returns `(pc.val + 1) % (n + 1)` and increments `State.updates` exactly when `pc.val == n`. No transition, hypothesis, bound, or theorem statement changed during attempts.

Positive theorem, exact statement:

```lean
theorem step_records_wrap {n : Nat} (pc : Fin (n + 1)) (state : State) :
    (step pc state).2.updates = state.updates +
      if (step pc state).1.val = 0 then 1 else 0
```

Nearby false claim tested with `fail_if_success colony` at `n = 1`, `pc = 0`, `updates = 0`:

```lean
(step (n := 1) ⟨0, by omega⟩ ⟨0⟩).2.updates = 1
```
The compiled control is its negation, proved by `decide`. This preserves the same transition and demonstrates a concrete counterexample.

## Attempt and outcome

The exact positive theorem body first ran `colony` directly. It failed with:

```
colony: the initial proof portfolio could not close this goal
```

The committed example retains a `fail_if_success colony` check and then proves the exact theorem using explicit case analysis, modular arithmetic, and simplification. This is not reported as `colony` success. No tactic change was needed or made.

An initial scratch attempt with `split <;> omega` failed because omega does not reason about the required modular nonzero fact; it exposed the need to derive `pc.val + 1 < n + 1` and reduce modulo with `Nat.mod_eq_of_lt`. A scratch version contained an unfinished proof and was discarded before the final build; the final artifact contains no `sorry` or `admit`.

## Commands and evidence

- `git rev-parse HEAD` → `c0681623823204dc02c5a63460c1e69cc2e3a196`
- `cd lean && lake build Colony` → success (12 jobs; existing unrelated linter warnings).
- `cd lean && lake env lean Colony/Examples/ModularCounterInvariant.lean` → first attempt failed on `colony`, as recorded above; also caught the initially mischosen control and an insufficient modulo proof.
- `cd lean && lake build Colony.Examples.ModularCounterInvariant` → success (4 jobs; two unused simp-argument warnings).
- Lean emitted `#print axioms step_records_wrap`: `[propext, Classical.choice, Quot.sound]`.
- SHA-256 of final example: `277f0cd90732dc1b974a2978713a45be6198dcd8296f8970d70cd6e0c92df2d6`.
- `lean/Colony/Tactic.lean` was not modified (SHA-256 `ec7cec60fb375eafc149a9c1bb1bdee712154bdce8319298b6221a8fcdabf858`).

## Assurance boundary

The final positive theorem is accepted by the local Lean elaborator/kernel via the normal Lake build and its axiom dependencies are reported above. The `colony` tactic does **not** prove it. No exported replay or `lake comparator` was run; no independent-kernel acceptance was obtained; no correspondence to Cardano execution is claimed. The theorem establishes only the stated mathematical one-step relation for `Fin (n + 1)`.
