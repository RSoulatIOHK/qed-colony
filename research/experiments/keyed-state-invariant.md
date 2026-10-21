# Keyed state invariant experiment

## Source revision

Base source revision: `b9ab00ff7cc8989db40ce002e7a6529c93143f09`.

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

The `colony` attempt did not close the theorem. The state is an unconstrained
list and the target depends on the recursive `update` and `sumExcept` functions.
The tactic does not perform the needed list induction and recursive unfolding
for this goal. The fallback proof splits on whether the current entry's key is
the updated key; simplification then uses the induction hypothesis in the
other-key case. The source-level guard makes the experiment fail if `colony`
starts proving the full theorem.

The file also includes a concrete computation showing that updating key `2`
from value `5` to `99` leaves the other-key sum at `18`, and a nearby false
`+ 1` property guarded to check that `colony` does not prove it.

## Commands and results

- `cd lean && lake env lean Colony.lean` — initially failed because the
  project's `Colony` modules had not yet been built into Lake's search path.
- `cd lean && lake build Colony` — succeeded (13 build jobs). This compiled the
  experiment and its guards, as well as the `Colony` import root. Existing
  unrelated linter warnings appeared in several example modules.

## Assurance limits

Successful Lean elaboration and Lake compilation establish kernel acceptance
of this theorem in the configured Lean environment. The concrete example is
non-vacuous for the stated list. This experiment does not establish exported
proof replay, independent-kernel acceptance, or correspondence to Cardano
execution; it is not a benchmark or security-boundary claim.
