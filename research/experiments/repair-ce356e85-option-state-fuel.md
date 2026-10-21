# REPAIR-ce356e85: fuel-bounded Option state procedure

## Example and result

`lean/Colony/Examples/OptionStateRecursion.lean` defines an Option-valued
command and recursive `runBounded`, which threads state through a list of
commands and stops on failure. `runTwo` calls it with semantic fuel exactly
`2`. The preserved theorem `runTwo_success_advances` states that success
implies the final state is at least the initial state plus two. The procedure
definition fixes the semantic execution bound; the existing `colony` tactic
has no separate search-depth argument. The theorem tries `colony` directly
under `fail_if_success`, which confirms that this tactic does not prove the
invariant; explicit Boolean case analysis then proves the unchanged statement.
An example confirms success is reachable. A neighboring false invariant
(`state + 3 ≤ finalState`) is attempted with `colony` under `fail_if_success`
and rejected through the same path.

## Reproduction and evidence

- Repository source revision: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
- Source material inspected: `52e4d5c7f56d965161f09dfed10806c00b3ec00a`.
- Pinned Lean toolchain: `leanprover/lean4:v4.35.0`.
- Exact check, from `lean/`: `lake build Colony.Examples.OptionStateRecursion`.
- Actual result: exit 0; `✔ [4/4] Built Colony.Examples.OptionStateRecursion (4.1s)`;
  `Build completed successfully (4 jobs).` This is Lean elaborator/kernel
  acceptance of the checked proofs, not exported replay, independent-kernel
  acceptance, or correspondence to Cardano execution.
- Example SHA-256: `5acabf57ea6bdec5e229e6112f25fb5f828b9633ba72da341e04805ac74b5e96`.
- `git diff --check`: exit 0.

The exact direct failed attempt was run from `lean/`:

```sh
sed 's/^  fail_if_success colony$/  colony/' Colony/Examples/OptionStateRecursion.lean > /tmp/OptionStateRecursion-direct.lean
lake env lean /tmp/OptionStateRecursion-direct.lean
```

The `sed` command exited 0. The Lean command exited 1 and printed:

```text
/tmp/OptionStateRecursion-direct.lean:37:2: error: colony: the initial proof portfolio could not close this goal
```

The failure is the current tactic's inability to establish the successful-run
invariant from this recursive Option procedure; the bounded semantic definition
itself compiles. No shared tactic code was changed.
