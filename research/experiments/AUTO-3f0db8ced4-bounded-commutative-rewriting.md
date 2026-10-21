# AUTO-3f0db8ced4: bounded commutative arithmetic search

## Scope and source

Base revision: `9b091914e32eac614f784c19fb2df9729ce4d9aa`.
Changed source: `lean/Colony/Tactic.lean` (SHA-256
`59110dea041530994e6e2d3a254b8dfd0c9b8b2dcdbf0226538a464061f1daf5`).
The only tactic change adds `ac_rfl` as a deterministic fallback inside the
existing arithmetic portfolio. This is bounded normalization using Lean's
generic associativity/commutativity reasoning; it names neither benchmark
theorems nor operator-specific commutativity lemmas. Existing local hypotheses
remain available to the portfolio. It is not an unbounded rewrite search.

The two benchmark statements were copied verbatim from the frozen NNG4 corpus:
`a + b = b + a` and `a + b + c = a + c + b` over `Nat`. Both are still proved
with exactly `by colony`; no benchmark source, statement, or policy was edited.

## Experiment

Temporary Lean input contained those two theorem declarations with `:= by
colony`, followed by these controls:

```lean
example : True := by
  fail_if_success (have : ∀ a b : Nat, a - b = b - a := by colony)
  fail_if_success (have : (0 : Nat) = 1 := by colony)
  trivial
```

The first control is a noncommutative subtraction equality; the second is an
intentionally invalid equality. `fail_if_success` compiled successfully,
confirming that `colony` left both propositions unsolved.

## Commands and outcomes

- `git rev-parse HEAD` → `9b091914e32eac614f784c19fb2df9729ce4d9aa`.
- `cd lean && lake build Colony` → exit 0, `Build completed successfully (13 jobs)`.
- `cd lean && lake env lean /tmp/auto3f0db8-test.lean` → exit 0; both
  commutativity theorems elaborated from exactly `by colony`, and both controls
  behaved as expected under `fail_if_success`.
- The test file printed axioms for the two positive theorems. Lean reported
  `[propext, Quot.sound]` for each. Elaborator/kernel acceptance was achieved
  under this local Lean toolchain. No exported replay or independent-kernel
  check was run.

An earlier control wrapped the false equality in a negation and introduced its
assumption; `colony` then succeeded by contradiction. That did not isolate a
noncommutative target, so it was discarded and replaced by the direct guarded
subtraction proposition above.

No `sorry`, `admit`, arbitrary axioms, native evaluation axioms, or disabled
kernel checks were introduced. No performance claim is made.
