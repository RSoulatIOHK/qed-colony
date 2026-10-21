# AUTO-ce3e7f2489: bounded Option recursion in a stateful command

## Scope and acceptance

Probe the existing `colony` tactic on an Option-valued recursive command with a
fixed semantic depth of two. Keep `runTwo_success_advances` and its assumptions
unchanged, show a successful run, and reject a nearby false invariant. No tactic
code is changed.

## Example and result

`lean/Colony/Examples/OptionStateRecursion.lean` defines `runBounded`, which
recurses on fuel, threads a natural-number state through Boolean commands, and
returns `none` on a failed command or missing input. `runTwo` invokes it with
fuel `2` and the original two commands. `runTwo_original_semantics` proves that
this wrapper equals the original two-step Option command for every input.

The unchanged theorem says `runTwo state first second = some finalState` implies
`state + 2 ≤ finalState`. The direct `colony` attempt fails; the checked source
records that result with `fail_if_success colony` and closes the theorem by
Boolean cases, simplification of the recursive definition, and `omega`.
`runTwo 0 true true = some 2` proves success is reachable. The stronger claim
with `state + 3 ≤ finalState` is refuted on that successful run, and a separate
`fail_if_success` check confirms `colony` does not prove it.

The bound `2` is a **semantic execution bound** in the command definition.
`colony` has no syntax for a tactic search-depth bound; none is claimed here.

## Source and exact checks

- Original base revision: `d1450e0f9dfa1170ce157c9ff32cf1d046b13b59`.
- Previous reviewed candidate revision: `99b68fafbd44fa23310618a29605125526820dda`.
- Current checkout revision: `99b68fafbd44fa23310618a29605125526820dda`,
  with the uncommitted example SHA-256
  `5c6c575c974f2ea23ee4af9f7df545c0dd9523bbf95e584b2177b87637ff1512`.
- Pinned toolchain: `leanprover/lean4:v4.35.0`.
- From `lean/`, `lake build Colony.Examples.OptionStateRecursion` exited 0:
  `✔ [4/4] Built Colony.Examples.OptionStateRecursion (13s)` and
  `Build completed successfully (4 jobs).` Both `fail_if_success` checks
  therefore observed tactic failure, and Lean accepted the explicit proofs.
- From `lean/`, writing `import Colony.Examples.OptionStateRecursion` followed
  by `#print axioms Colony.Examples.runTwo_success_advances` and
  `#print axioms Colony.Examples.runTwo_original_semantics` to
  `/tmp/OptionStateRecursion-axioms.lean`, then running
  `lake env lean /tmp/OptionStateRecursion-axioms.lean`, exited 0. Each theorem
  reported only Lean's `propext` and `Quot.sound` axioms; no new axiom was used.
- `git diff --check` exited 0.

To reproduce the direct failed attempt on the previous candidate, run from the
repository root:

```sh
git show 99b68fafbd44fa23310618a29605125526820dda:lean/Colony/Examples/OptionStateRecursion.lean | sed 's/^  fail_if_success colony$/  colony/' > /tmp/OptionStateRecursion-prior-direct.lean
cd lean
lake env lean /tmp/OptionStateRecursion-prior-direct.lean
```

The final command exited 1 with the exact diagnostic:

```text
/tmp/OptionStateRecursion-prior-direct.lean:19:2: error: colony: the initial proof portfolio could not close this goal
```

For the current bounded version, from `lean/`:

```sh
sed 's/^  fail_if_success colony$/  colony/' Colony/Examples/OptionStateRecursion.lean > /tmp/OptionStateRecursion-bounded-direct.lean
lake env lean /tmp/OptionStateRecursion-bounded-direct.lean
```

The second command exited 1 with:

```text
/tmp/OptionStateRecursion-bounded-direct.lean:35:2: error: colony: the initial proof portfolio could not close this goal
```

An intermediate attempt to prove `runTwo_original_semantics` with `rfl` failed:
the two sides were not definitionally equal while the Boolean commands remained
variables. Splitting both Booleans and simplifying proved the equivalence.

The successful build establishes Lean elaborator/kernel acceptance of the
explicit proofs under the pinned toolchain. It does not establish exported
replay, independent-kernel acceptance, or correspondence to Cardano execution.
