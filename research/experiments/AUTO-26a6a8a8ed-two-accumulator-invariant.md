# AUTO-26a6a8a8ed: bounded induction for a two-accumulator invariant

## Scope and exact example

Added `Colony.Examples.copyIntoBoth` in
`lean/Colony/Examples/TwoAccumulatorInvariant.lean`. It walks an input list and
prepends each element to both threaded accumulators. Its recursive equations
are marked `[simp]` so the existing `colony` simplification and induction
portfolio can use them. No tactic implementation was changed.

The exact theorem statement is:

```lean
theorem copyIntoBoth_lengths (xs left right : List Nat) :
    (copyIntoBoth xs left right).1.length = xs.length + left.length ∧
    (copyIntoBoth xs left right).2.length = xs.length + right.length
```

It has no additional assumptions or bounds. The theorem is proved directly by
`colony`. The nearby false proposition adds one to the first output length:

```lean
(copyIntoBoth xs left right).1.length = xs.length + left.length + 1
```

The example wraps a `by colony` proof of that false proposition in
`fail_if_success`, confirming the tactic leaves it unsolved. No `sorry`,
`admit`, or axioms were introduced.

## Commands and actual results

Using the project toolchain pinned in `lean/lean-toolchain`:
`leanprover/lean4:v4.35.0`.

From the `lean/` project directory, the build command was:

```sh
lake build Colony
```

It exited 0. Relevant output:

```text
✔ [9/11] Built Colony.Examples.TwoAccumulatorInvariant (4.2s)
✔ [10/11] Built Colony (4.0s)
Build completed successfully (11 jobs).
```

There were existing warnings in other examples and unused-variable warnings
for parameters only used implicitly by the negative-control tactic block.
The first attempt without `[simp]` on `copyIntoBoth` exited 1 because
`colony` could not close the theorem; adding the simplification attribute
allowed the unchanged theorem to close.

The source is imported from `Colony.lean` so this `lake build Colony` checks
the example. The negative control is elaborated as part of that same successful
build; failure of `colony` is required by `fail_if_success`.

## Assurance and limits

The positive proof and negative control were accepted by Lean's elaborator and
kernel. Assurance is **elaborator kernel acceptance only**. No exported replay,
independent-kernel acceptance, or correspondence to Cardano execution is
claimed. This is a small synthetic example, not a benchmark or performance
claim.
