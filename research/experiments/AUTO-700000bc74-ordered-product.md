# AUTO-700000bc74: ordered-product monotonicity probe

## Scope

Probe the tactic's ordered-goal fallback for natural-number goals `a * t ≤ b * t` from `h : a ≤ b`. The implementation adds one deterministic attempt using Lean's existing `Nat.mul_le_mul_right` theorem, followed by `assumption`. It does not inspect theorem names or benchmark identities. The assumption requirement prevents it from solving a goal by inventing an order premise.

## Source

Base/source revision before this experiment: `9b091914e32eac614f784c19fb2df9729ce4d9aa`.

## Commands and results

All commands below were run from the repository root unless noted.

1. `git rev-parse HEAD` → `9b091914e32eac614f784c19fb2df9729ce4d9aa`.
2. `cd lean && lake build Colony` → exit 0, `Build completed successfully (13 jobs).` Existing linter warnings appeared in example modules.
3. Valid and supported reversed controls, in a temporary `lean/Auto700000bc74Probe.lean` containing:

   ```lean
   import Colony
   theorem ordered_product (a b t : Nat) (h : a ≤ b) : a * t ≤ b * t := by colony
   theorem reversed_with_support (a b t : Nat) (h : b ≤ a) : b * t ≤ a * t := by colony
   ```

   Command: `cd lean && lake env lean Auto700000bc74Probe.lean` → exit 0, no diagnostics. This checks both elaborated proofs with Lean's kernel.

4. False control appended to that temporary file:

   ```lean
   theorem false_ordered_goal (a b t : Nat) : b * t ≤ a * t := by colony
   ```

   Command: `cd lean && lake env lean Auto700000bc74Probe.lean` → exit 1 with `error: colony: the initial proof portfolio could not close this goal`. The temporary source was removed afterward.

5. Initial environment probe `cd lean && timeout 8 lake env lean /tmp/probe.lean` → exit 124 because the source was outside Lake's package root. This was a harness-location error, not a tactic failure; subsequent probes were placed temporarily inside `lean/` and removed.

## Assurance and limits

Lean 4.35.0's elaborator and kernel accepted the two valid `by colony` proofs. The invalid reversed goal without a supporting hypothesis remains unsolved. No `sorry`, `admit`, axiom, native evaluation axiom, or disabled kernel check was added. This is elaborator/kernel acceptance only; no exported proof replay, independent-kernel verification, or Cardano-execution correspondence was performed.

The probe uses `Nat.mul_le_mul_right`, so its scope is natural-number multiplication. It does not establish generic monotonicity for arbitrary ordered semirings or other types. The referenced unchanged benchmark theorem was not present in the visible `lean/Challenge.lean` or `lean/SeedProofs.lean`; the shape was exercised directly in a temporary test file, without changing challenge statements.
