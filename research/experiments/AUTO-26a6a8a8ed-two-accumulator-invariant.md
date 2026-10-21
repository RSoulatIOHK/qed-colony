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

From the `lean/` project directory, compile the example directly:

```sh
lake env lean Colony/Examples/TwoAccumulatorInvariant.lean
```

It exited 0. The only output was three unused-variable warnings at line 18
for `xs`, `left`, and `right` in the negative-control wrapper. Those variables
occur in a `fail_if_success` block, which the linter does not count as explicit
references. The successful compile elaborated the unchanged theorem proof and
required the false proof attempt to fail.

The direct Lake target command was also run:

```sh
lake build Colony.Examples.TwoAccumulatorInvariant
```

It exited 0 and replayed the cached target:

```text
⚠ [4/4] Replayed Colony.Examples.TwoAccumulatorInvariant
Build completed successfully (4 jobs).
```

The failed experiment without `[simp]` was reproduced without editing the
source:

```sh
sed '/^@\[simp\]$/d' Colony/Examples/TwoAccumulatorInvariant.lean | lake env lean --stdin
```

It exited 1 with `<stdin>:15:2: error: colony: the initial proof portfolio
could not close this goal`, plus the same unused-variable warnings. Thus the
current tactic needs the recursive equations available to simplification to
close this unchanged theorem.

`Colony.lean` does not import this example. Both commands above check the
example directly. The negative control is elaborated as part of the successful
compile; failure of `colony` is required by `fail_if_success`.

The same false statement was also attempted directly from `lean/`:

```sh
lake env lean --stdin <<'LEAN'
import Colony.Examples.TwoAccumulatorInvariant
open Colony.Examples
example (xs left right : List Nat) :
    (copyIntoBoth xs left right).1.length = xs.length + left.length + 1 := by
  colony
LEAN
```

It exited 1 with `<stdin>:5:2: error: colony: the initial proof portfolio
could not close this goal`. This confirms the false variant is not proved by
`colony` on its own.

## Assurance and limits

The positive theorem and the wrapper around the negative control were accepted
by Lean's elaborator and kernel. Assurance is **elaborator kernel acceptance
only**. No exported replay,
independent-kernel acceptance, or correspondence to Cardano execution is
claimed. This is a small synthetic example, not a benchmark or performance
claim.
