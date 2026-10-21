# Keyed state invariant experiment

## Source revision

Base source revision: `b9ab00ff7cc8989db40ce002e7a6529c93143f09`.
The tested candidate is the working tree at
`89686d40f5dec88f207714aa29f5dfb504202ff0`, with the example file's
SHA-256 `77ff0c80d0f888c4a4b1fe6470ba1baca121767a83fd7978afe44790f88075e8`.
The working-tree edit adds the concrete state check below; the build result
refers to this tested candidate, before this research record was updated.

## Procedure and exact theorem

The isolated example represents state as `List (Nat × Nat)`. `update key value`
replaces the first entry whose key matches, leaves later entries untouched, and
returns the original state if there is no match. It is structurally recursive
on the list, so it performs at most one step per list element. `sumExcept key`
sums values for entries whose key is not `key`.

Exact theorem statement:

```lean
theorem update_preserves_sum_except (state : State) (key value : Nat) :
    sumExcept key (update key value state) = sumExcept key state
```

There are no additional assumptions. The theorem is proved by list induction
after guarding the `colony` attempt with `fail_if_success`.

## Tactic result and reason

The `colony` attempt did not close the theorem. Its portfolio does try generic
induction on a list (and natural numbers), followed by `simp_all` and `omega`.
For this goal that attempt does not close the key-equality conditional in the
recursive `update` and `sumExcept` equations. The fallback proof explicitly
splits on whether the current entry's key is the updated key; simplification
then uses the induction hypothesis in the other-key case. The source-level
guard makes the experiment fail if `colony` starts proving the full theorem.

The file also includes a concrete conjunction checking that updating key `2`
from value `5` to `99` produces the state
`[(1, 7), (2, 99), (3, 11)]` and leaves the other-key sum at `18`. A nearby
false `+ 1` property is guarded to check that `colony` does not prove it.

## Commands and results

- `cd lean && lake env lean Colony.lean` — initially failed before the
  project's `Colony` modules were built into Lake's search path; succeeded
  after the build below on the tested candidate.
- `cd lean && lake build Colony` — succeeded (13 build jobs). This compiled the
  experiment and its guards, as well as the `Colony` import root, on the tested
  candidate above. Existing linter warnings appeared in example modules.
- `printf 'import Colony.Examples.KeyedStateInvariant\n#print axioms Colony.Examples.KeyedStateInvariant.update_preserves_sum_except\n' | lake env lean --stdin`
  (from `lean/`) — succeeded; Lean reported `[propext]`.
- `node --check observatory/dist/app.js` — succeeded.
- `python3 -m unittest discover -s tests -v` — failed: 286 tests ran, with
  2 failures and 13 errors. The output includes sandbox-denied socket binds
  and unrelated process-control test failures; no keyed-state Lean failure was
  reported.
- `python3 scripts/evaluate_lean.py --output /tmp/qed-keyed-state-benchmark-results.json`
  — succeeded. The local pilot reported `colony` certified 8/8 existing
  positive challenges, rejected the existing false-property challenge with
  its witnesses certified, and had 0 evidence errors. This experiment is not
  one of those scored challenges.
- `git diff --check` — succeeded.

## Assurance limits

Successful Lean elaboration and Lake compilation establish kernel acceptance
of this theorem in the configured Lean environment. `#print axioms` reports
only standard `propext`; no `sorry`, `admit`, or new axioms are used. The
concrete example checks both the changed state and the preserved sum. This
experiment does not establish exported
proof replay, independent-kernel acceptance, or correspondence to Cardano
execution; it is not a benchmark or security-boundary claim.
