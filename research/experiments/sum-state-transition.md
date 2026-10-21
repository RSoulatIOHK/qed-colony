# Bounded Sum branching for state-transition proofs

## Source identity

- Base/source revision: `3a7c71e41ba1a29df363e8847fbe5a01e3a96bf8` (`git rev-parse HEAD` before edits; this experiment was run as an uncommitted working-tree change).
- Lean toolchain: repository `lean/lean-toolchain` (Lean 4.35.0).
- Changed source: `lean/Colony/Tactic.lean`, `lean/Colony/Examples/SumStateTransition.lean`, and `lean/Colony.lean`.

## Experiment

`colony` now scans visible local declarations in context order for `Sum α β`. It tries one candidate at a time, splits it, and runs the existing arithmetic portfolio (`omega`, `simp_all <;> omega`, `decide`) on every branch. A failed candidate restores the saved tactic state before trying the next candidate.

The example's transition returns `Sum Nat Nat`; concrete reductions cover `.inl` and `.inr`. The generic payload-successor invariant is proved using `by colony`, and a corollary applies it to every transition result. The nearby `fail_if_success` assertion checks that the tactic cannot prove the stronger false bound `next > 1` for arbitrary results.

## Commands and results

- `lake env lean Colony/Examples/SumStateTransition.lean` before building dependencies: **failed**, `unknown module prefix 'Colony'` because the package `.olean` files had not yet been built.
- `lake build` from `lean/`: **passed**, 13 jobs. Existing linter warnings were emitted in unrelated examples; the new example emitted no warnings.
- `lake env lean Colony/Examples/SumStateTransition.lean` from `lean/` after the build: **passed**. The `fail_if_success` check accepted, so the false target was rejected by `colony`; both constructor witnesses reduced by `rfl`.
- A first proof shape using `result = step count true` as a reachability hypothesis did not close with the arithmetic portfolio. The final positive theorem uses the stronger generic payload invariant, with a separate corollary connecting it to `step`.

## Axioms and assurance

The Lean command printed:

```text
'Colony.Examples.SumStateTransition.payload_successor_exceeds_itself' depends on axioms: [propext, Quot.sound]
```

These are Lean's standard logical axioms used in elaborated library proofs; no `sorry`, `admit`, custom axiom, native evaluation axiom, or disabled kernel check was introduced. Assurance achieved: Lean elaborator/kernel acceptance of this theorem in the repository build. No exported replay, independent-kernel check, or correspondence to Cardano execution is claimed.
