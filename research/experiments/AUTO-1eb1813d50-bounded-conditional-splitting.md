# AUTO-1eb1813d50: bounded conditional splitting during list induction

## Scope and source identity

Base revision: `3b11188d52ad5ff8c1f1885508b44c1d6e584f66`.
The working tree was derived from that revision. The requested theorem statement,
definitions, assumptions, bounds, benchmark files, evaluator files, and root
import were not changed. The theorem body was changed to exactly `by colony`.

## Candidate design

The candidate code adds a deterministic expression traversal for the first
visible `ite`/`dite` condition and attempts one decidable `byCasesDec` split
per induction branch. The finite split bound is one condition per branch. Each
split requires both children to close; failure is caught by the enclosing
candidate-state snapshot and restores that tactic state. No recursive `colony`
invocation is used.

## Attempts and outcomes

- `cd lean && lake build Colony` on the base proof body: succeeded before the
  experiment edits.
- First implementation compile: failed because Lean 4.35 represents the
  expression head as a `Name` and `byCasesDec` returns a pair. Both API errors
  were corrected; the tactic module then compiled.
- With the theorem changed to exactly `by colony`, `cd lean && lake build Colony`
  failed at `KeyedStateInvariant.lean:23` with `colony: the initial proof
  portfolio could not close this goal`.
- A generic induction route then intercepted a pre-existing list-state example;
  the build also failed there. That route was removed from the active portfolio.
- A subsequent attempt to expose conditions with simplification still did not
  close the keyed theorem. The current worktree has not passed a full build.

## Exact current checks

Command: `cd lean && lake build Colony`.
Outcome: failed. The tactic source compiled in the attempted builds, but
`Colony.Examples.KeyedStateInvariant` still failed on the `by colony` theorem;
a prior intermediate build also showed the regression in `ListStateInvariant`.
No successful final build was obtained.

The concrete valid update example remains in the source, and the false nearby
`+ 1` claim remains under `fail_if_success`; because compilation fails earlier,
these guards have not been verified in the final candidate.

## Assurance and limitations

No successful theorem elaboration was established for this candidate. Therefore
there is no kernel-acceptance claim for the requested theorem, and no exported
replay, independent-kernel, or Cardano correspondence claim. The requested
acceptance criteria are not met. No `sorry`, `admit`, or axiom was introduced.
