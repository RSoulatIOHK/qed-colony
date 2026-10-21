# REPAIR-ae48abbea8c342b78741992574cc3c5c: bounded list fallback on current main

## Source and scope

Base/current main revision: `647f0bc377bda30268d49690e26694dc7332125c`.
Source candidate inspected: public PR #45 head
`365b03739c55a741d2e2856e7c54a6b1fe3491ae` (available as a local Git object).
This fresh, uncommitted repair ports its bounded list-candidate handling and
focused example to the current source. The Lean edits are limited to
`lean/Colony/Tactic.lean` and the new
`lean/Colony/Examples/BoundedListProcess.lean`. The existing
`lean/Colony/Examples/ListStateInvariant.lean`, procedure definitions in
`lean/Colony/Procedures/ListState.lean`, and `lean/Colony.lean` are unchanged.
The focused example imports `Colony.Tactic` and the existing ListState module
directly; no umbrella import was added. Research changes comprise this report.
No evaluator, policy, benchmark, challenge, CI, or protected files changed.

SHA-256 of the checked source files:

| File | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `f3d0073f6f697a4f5e1edfa10a72095ad4c5174a447f3919e2e4f18127250553` |
| `lean/Colony/Examples/BoundedListProcess.lean` | `7c22a57ced362ad2422eb91a21dfda560ea5ac79f59235666de492ef6e2e65dc` |
| `lean/Colony/Examples/ListStateInvariant.lean` | `10746c7bc8ee2ce9ba403c269c994b4baa47fe45cccae61bf64715a52b9762e8` |
| `lean/Colony/Procedures/ListState.lean` | `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0` |
| `lean/Colony.lean` | `fa04674632606dd1facf16ac614d26e1ff6a0d47075e718bd54f6e0995b84c91` |

Toolchain: Lean 4.24.0, commit
`797c613eb9b6d4ec95db23e3e00af9ac6657f24b`, Lake 5.0.0-src+797c613.

## Implementation and theorem evidence

The list-state fallback counts visible locals of type `List ListCommand`.
Exactly one candidate receives exactly one list induction attempt, with other
non-propositional locals generalized. Branch solving uses
`simp_all [process, step] <;> omega` and can split a command local when the
initial branch solve fails. The attempt has a saved tactic state; failure
restores it. If any command-list candidate existed, failure or ambiguity ends
the list-specific route, so the generic list/Nat induction cannot retry a
different candidate. Ambiguous candidates make zero attempts.

`extended_process_preserves_list_state_invariant` is the focused positive
theorem: from the unchanged equality assumption, an arbitrary command list
followed by `record 1` and `skip` preserves equality. Its statement, assumptions,
and the existing `ListCommand`, `step`, and `process` definitions are not
altered. It closes with `by colony`; `#print axioms` reports
`[propext, Quot.sound]`. The focused example also proves a concrete negative
witness: processing `[record 1]` from `⟨0, 0⟩` gives both counters value `1`, so
they cannot differ by one. `fail_if_success colony` rejects the false universal
offset property, a failed property with an unrelated Nat candidate, and an
ambiguous two-command-list property.

## Commands and actual results

From `lean/`:

```sh
lake build Colony.Tactic Colony.Examples.BoundedListProcess Colony.Examples.ListStateInvariant
lake env lean Colony/Examples/BoundedListProcess.lean
lake env lean Colony/Examples/ListStateInvariant.lean
```

All commands exited 0. The Lake build completed successfully (5 jobs). Direct
focused elaboration printed, in order:

```text
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=success
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=failure; state=restored; reason=colony: induction branch lacks a command constructor
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=failure; state=restored; reason=colony: induction branch lacks a command constructor
[Colony.listProcess] candidates=2; attempts=0; ambiguous command lists
'Colony.Examples.extended_process_preserves_list_state_invariant' depends on axioms: [propext, Quot.sound]
```

The existing ListState target also elaborated successfully, with two preexisting
unused-variable warnings. `git diff --check` exited 0. No evaluator or umbrella
build was run; only the requested direct tactic and list-state targets were
checked.

## Failed attempts and effects

The source candidate's historical work had exceeded scope by adding the focused
example to the umbrella import list; that import is absent here. Its recorded
scope correction also identified generic induction fallthrough as an invalid
bounded-search shape; this repair explicitly prevents that fallthrough when a
command-list candidate is present. During these checks the positive candidate
succeeded once; false-property and unrelated-Nat cases each made one attempt,
failed to find a command constructor on a remaining branch, restored state,
and were rejected by `fail_if_success`. Two candidates were rejected without
attempting induction. These are intentional negative controls, not failed
positive proofs.

The focused module imports the tactic and existing procedure module directly.
The tactic imports `Std.Tactic`; solving explicitly unfolds `process` and
`step` through `simp_all` before `omega`. Thus shared-import simplifier effects
are part of this result; no global simp attribute was added. The focused trace
option is local to the focused module. No claim is made that the result is
independent of the shared import environment.

## Assurance and limits

The positive theorem is an ordinary elaborated Lean proof term accepted by the
Lean kernel on the stated toolchain, with reported dependencies
`[propext, Quot.sound]`. No `sorry`, `admit`, new axiom, native evaluation
axiom, or disabled kernel check was introduced. This does not establish
exported replay, independent-kernel acceptance, correspondence to Cardano
execution, runtime bounds, or performance improvement. The one-candidate bound
limits structural induction attempts, not simplifier runtime or the number of
generated proof obligations.
