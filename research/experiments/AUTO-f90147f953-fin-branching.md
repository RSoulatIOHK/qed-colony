# AUTO-f90147f953: bounded `Fin` branching

## Scope and acceptance

Probe one deterministic `Fin` case split for an index dependent invariant. The
fallback selects at most the first eligible local `Fin (Nat.succ n)`, makes
the zero/successor split, and commits only if `simp_all <;> omega` closes every
branch. Any failed attempt restores the saved tactic state. No theorem statement,
assumption, bound, challenge, or evaluation policy was changed.

## Experiment

Added the generic fallback to `lean/Colony/Tactic.lean` and the example in
`lean/Colony/Examples/FinBranching.lean`. `marker_bounded` closes with exactly
`by colony`; it exercises the value of a local finite index in a bound. A
neighboring false claim, `marker i < 1`, is guarded by `fail_if_success colony`.
Closed witnesses at bound `2` check both `marker 0 = 0` and `marker 1 = 1`.
The successor witness shows a concrete counterexample to the false claim.

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
- After adding the closed successor witness, `simp [marker]` left the concrete
  `Fin.cases` expression unsolved. `decide` closed that witness; the target
  invariant still uses only `colony`.

## Evidence

- Base source revision: `713fa5e229b4d5a19afa7adce2767cb2c9f38723`.
- Candidate HEAD: `1e7038fb80139959afccf79fa1888ad7e2de53e6`, plus the
  uncommitted witness and note edits. SHA-256 of the tested tactic file
  `lean/Colony/Tactic.lean`:
  `ae184762f68cc062125d9c74339882eace70b96033b43d5219d5acf69c4f156b`.
  SHA-256 of the tested example file
  `lean/Colony/Examples/FinBranching.lean`:
  `b7ef9293cc72f1e0bf53713474dd929e284f4d1d238252d5f3df293380ed3e60`.
- `cd lean && lake build Colony`: exit 0, build completed successfully (14
  jobs); existing examples built. Existing linter warnings were emitted.
- `cd lean && lake env lean Colony/Examples/FinBranching.lean`: exit 0 on the
  tested file; the invariant, false-control guard, and both closed witnesses
  elaborated. The printed axiom dependencies for `marker_bounded` are
  `[propext]`. The false-control example produced an unused-variable linter
  warning for `i`.
- `cd lean && lake env lean Colony/Examples/BooleanBranching.lean`, and the
  analogous commands for `OptionBranching.lean`, `ProductStateTransition.lean`,
  and `OrderedProduct.lean`: each exited 0. The latter three emitted existing
  linter warnings; the four printed `OrderedProduct` axiom lists were empty.
- `git diff --check`: exit 0.

The evidence supports Lean elaborator kernel acceptance for the example proof
terms. It does not establish exported replay, an independent kernel check, or
correspondence to Cardano execution.
