# AUTO-4b88e8dd25: bounded equality-conditional splitting

## Scope and source

Base source revision: `e520c39bbf6989f33dad692560babfaa49aed440`.
The working tree was based on this revision; no commit was created. The attempted change adds a deterministic local-context search over at most eight same-typed local pairs at each node, with split depth two. Each candidate is wrapped in `saveState`/restore, and recursive list induction branches call the splitter after the generic simplifier/arithmetic attempt. The new fixture is `Colony.Examples.RecursiveKeyedInvariant`.

## Commands and observed results

- `git rev-parse HEAD` — `e520c39bbf6989f33dad692560babfaa49aed440`.
- `lake build Colony` (from `lean/`) — failed during the first attempt because of tactic elaboration errors (`do` nesting and `Bool`/`Unit` mismatch). After those errors were corrected, the build showed the existing `Colony.Examples.ListStateInvariant` failure because the command-constructor fallback had been removed. That fallback was restored.
- `lake build Colony` after restoring the fallback — existing targets shown in output, including `Colony.Examples.ListStateInvariant`, compiled; the build failed because `Colony.Examples.RecursiveKeyedInvariant` did not close its positive theorem with `colony`.
- `lake build Colony.Examples.RecursiveKeyedInvariant Colony` — failed at `RecursiveKeyedInvariant.lean:17` with `colony: the initial proof portfolio could not close this goal`.
- `lake env lean Colony/Examples/RecursiveKeyedInvariant.lean` (from `lean/`) — same failure at line 17.
- `git diff --check` — passed.

Earlier failed attempts are preserved here: the first fixture over a list of key/value pairs could not expose the key projection as a local term; a simpler list-of-natural-numbers fixture still failed because the current branch search did not close the equality-split goals. No accepted theorem proof was obtained.

## Assurance and limitations

The intended positive theorem has **not** been certified and the acceptance criteria are not met. Consequently there is no theorem axiom report to claim for that result. The negative `fail_if_success` fixture does not establish positive correctness. No `sorry`, `admit`, or new axiom was introduced. There was no exported replay, independent-kernel check, or Cardano execution correspondence check. Lean 4 toolchain is pinned by `lean/lean-toolchain` to `leanprover/lean4:v4.35.0`.
