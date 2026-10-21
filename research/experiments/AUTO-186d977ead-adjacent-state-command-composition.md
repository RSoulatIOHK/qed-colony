# AUTO-186d977ead: strict sequential state-command composition

## Scope and exact theorem

The example adds one invariant theorem for two adjacent commands. `ListState`,
`ListCommand`, and `step` are unchanged; the only assumption is the stated
initial counter equality. The exact declaration is:

```lean
theorem adjacent_steps_preserve_list_state_invariant
    (state : ListState) (first second : ListCommand)
    (h : state.balance = state.recorded) :
    (step (step state first) second).balance =
      (step (step state first) second).recorded
```

## Experiment and result

The existing `colony` tactic could not prove this exact target. The declaration
contains `fail_if_success` around `colony` on the same proposition, so the
successful Lean build records the failure without changing the theorem. The
bounded example-level follow-up splits the two finite command constructors and
closes the four cases by simplification and `omega`. This is a proof script in
the example, not a change to the tactic portfolio.

A neighboring `fail_if_success` applies `colony` to the false variant with
`+ 1` on the final recorded count. Its successful elaboration confirms that
`colony` rejects that attempted proof. No failed external command or diagnostic
was retained; the in-source failure checks are the recorded reproductions.

## Source identity and commands

- Base Git revision: `261144d5725caf0e6e3ef514a034f3a25183041c`.
- Changed file SHA-256: `lean/Colony/Examples/ListStateInvariant.lean`:
  `13298e6edcb2c0cf36f124141baaa3cfb7db4acf465e6acadb3d03f7701b3d7b`.
- Unchanged definition SHA-256 values:
  `lean/Colony/Procedures/ListState.lean`:
  `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0`;
  `lean/Colony/Tactic.lean`:
  `d193f91238ab9d7a49856df2430588b56246fafd73f8036015b0facf47002a88`.
- `cd lean && lake build Colony`: exit 0; Colony, Boolean branching, and
  list-state examples built.
- `cd lean && lake build`: exit 0; all 10 targets built, including
  `SeedProofs`, so the existing R003 frontier and project targets continue to
  build. The example produced only the two pre-existing unused-parameter
  warnings in the older false check.
- `git diff --check`: exit 0.
- Toolchain: `leanprover/lean4:v4.35.0`.

## Assurance and limits

The positive theorem elaborated and was accepted by Lean's kernel in the
successful build. `colony` failed on the positive target and rejected the
nearby false proof attempt, as checked with `fail_if_success`. No exported
replay, independent-kernel, or Cardano-execution correspondence was checked.
This is one local example, not a benchmark or broader verification claim.
