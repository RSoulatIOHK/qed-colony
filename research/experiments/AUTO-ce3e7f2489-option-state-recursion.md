# AUTO-ce3e7f2489: bounded Option recursion in a stateful command

## Example and outcome

`lean/Colony/Examples/OptionStateRecursion.lean` defines a command that returns
`none` on rejection and `some (state + 1)` on success. `runTwo` threads the
state through exactly two commands, stopping on failure. The unchanged theorem
states that a successful run advances the initial state by at least two.

The existing `colony` tactic did not prove this invariant. Its exact attempt is
recorded by `fail_if_success colony` in the theorem; the theorem is then proved
by splitting the two Boolean commands and simplifying the original procedure.
The neighboring false claim `state + 3 ≤ finalState` is also passed through
`colony` under `fail_if_success` and rejected.

## Reproduction and evidence

- Source revision before this isolated change: `d1450e0f9dfa1170ce157c9ff32cf1d046b13b59`.
- Pinned Lean toolchain: `leanprover/lean4:v4.35.0` (`lean/lean-toolchain`).
- Exact check: `cd lean && lake build Colony.Examples.OptionStateRecursion`.
- Result: exit 0; module compiled. The positive `colony` attempt was captured
  by `fail_if_success`; a preceding direct attempt exited 1 with
  `colony: the initial proof portfolio could not close this goal`.
- Changed example SHA-256: `081c2756b0cfe9c228963f2b3b5fc0331ddb8fd2c560d72087011bc541d25ff9`.
- `git diff --check`: exit 0.

Lean accepted the explicit example proof in its kernel. This checks neither
exported replay nor an independent kernel or correspondence to Cardano
execution. The experiment demonstrates a limitation of the current tactic on
this example, not a general result about Option procedures.
