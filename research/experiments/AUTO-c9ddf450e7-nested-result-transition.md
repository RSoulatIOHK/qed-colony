# AUTO-c9ddf450e7: nested result transition splitting

## Scope and result

This isolated example uses `Option (Except Failure Nat)`, with two distinct
error constructors and a successful natural value. The complete transition is
preserved in the theorem's specification through `step`:

- no response adds three retries;
- an error adds two retries;
- a successful result adds its value plus one.

The positive theorem proves that every response advances the retry count. The
proof explicitly cases on the outer `Option` and inner `Except`/`Failure`, then
uses `colony` on the resulting arithmetic goals. This exercises `colony`'s
existing arithmetic portfolio at constructor depth one per invocation; it does
not establish automatic recursive splitting of the nested type. A direct
`by colony` attempt on `step retries response > retries` failed because the
named transition definition and nested match were not reduced/split by the
current tactic. That failed experiment is not in the final source.

A nearby false claim, that every response advances by more than three, is
rejected under `fail_if_success`.

## Evidence

- Base/source revision: `6726233302f4fc7f9f3aeee745002813ef6b38bb`.
- Command (from `lean/`): `lake build Colony`.
- Outcome: command returned partial output showing successful builds of
  `Colony.Procedures.ListState` and `Colony.Tactic`; the tool call reached its
  30-second time limit before a final exit status, so a completed full build is
  not claimed.
- Command (from `lean/`):
  `lake env lean Colony/Examples/NestedResultTransition.lean`.
- Outcome: exit code 0. Lean emitted unused-simp-argument warnings for two
  `simp only [step]` calls in branches where the match had already reduced,
  plus unused-variable warnings in the deliberately false `True` example.
- Assurance: Lean elaborator kernel acceptance of the example and its proofs.
  No exported replay, independent-kernel check, or Cardano execution
  correspondence was measured.
- Direct automatic-split experiment: the initial `by colony` proof failed with
  `colony: the initial proof portfolio could not close this goal`; this
  demonstrates a current tactic limitation, not a negative theorem result.
