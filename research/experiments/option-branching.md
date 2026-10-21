# Bounded `Option` case splitting

## Scope

Add one deterministic fallback to `colony`: try eligible local `Option α`
declarations in local-context order, committing to at most one split. Each
`none`/`some` branch is closed with the existing arithmetic portfolio. A failed
candidate restores the tactic state before trying the next candidate.

## Source and experiment

- Source revision before this change: `e1892b16c65d85d960b079970c5547cc050bb978`
- Command: `lake build Colony` (run from the `lean/` project directory)
- Result: exit code `0`; `Build completed successfully (9 jobs).`
- Lean also emitted existing unused-variable warnings in
  `Examples/ListStateInvariant.lean`, and unused-variable warnings for the
  intentionally irrelevant option and negative example parameter in
  `Examples/OptionBranching.lean`.
- Assurance: Lean elaborator kernel acceptance only.

The build includes a positive `Option Nat` theorem proved with `by colony`, a
theorem whose first option candidate is irrelevant and fails before the second
candidate succeeds, and an intentionally false proposition rejected under
`fail_if_success`. No failed build experiments were recorded.
