# AUTO-f90147f953: bounded `Fin` branching

## Scope and acceptance

Probe one deterministic `Fin` case split for an index dependent invariant. The
fallback selects at most the first eligible local `Fin (Nat.succ n)`, makes
the zero/successor split, and commits only if `simp_all <;> omega` closes every
branch. Any exception restores the saved tactic state. No theorem statement,
assumption, bound, challenge, or evaluation policy was changed.

## Experiment

Added the generic fallback to `lean/Colony/Tactic.lean` and the example in
`lean/Colony/Examples/FinBranching.lean`. `marker_bounded` closes with exactly
`by colony`; it exercises the value of a local finite index in a bound. A
neighboring false claim, `marker i < 1`, is guarded by `fail_if_success colony`.
The explicit concrete witness checks `marker 0 = 0` by simplification.

## Attempts and observations

- Directly running Lean on the example before building the library failed with
  `unknown module prefix 'Colony'`; building `Colony` first supplied the
  required module artifacts.
- The first filter inspected a weak-head-normalized local type. Lean unfolded
  `Fin` there, so that filter missed the candidate. Inspecting the local type
  before weak-head normalization fixed candidate recognition.
- A first example written as `Fin (n + 1)` did not match the successor-index
  eliminator. The final example uses the definitionally explicit
  `Fin (Nat.succ n)` supported by this bounded fallback.
- A temporary helper characterization theorem was removed. The final scored
  invariant has no helper proof and uses exactly `by colony`.

## Evidence

- Base source revision: `713fa5e229b4d5a19afa7adce2767cb2c9f38723`.
- `cd lean && lake build Colony`: exit 0, build completed successfully (14
  jobs); existing examples built. Existing linter warnings were emitted.
- `cd lean && lake env lean Colony/Examples/FinBranching.lean`: exit 0; the
  invariant, false-control guard, and concrete witness elaborated. The printed
  axiom dependencies for `marker_bounded` are `[propext]`.
- `cd lean && lake env lean Colony/Examples/OptionBranching.lean`: exit 0.
- A combined direct Lean run of Fin, Option, Boolean, and product focused
  examples began successfully, but exceeded the command time window before
  returning all results. Boolean and product examples were also built by
  `lake build Colony`.

The evidence supports Lean elaborator kernel acceptance for the example proof
terms. It does not establish exported replay, an independent kernel check, or
correspondence to Cardano execution.
