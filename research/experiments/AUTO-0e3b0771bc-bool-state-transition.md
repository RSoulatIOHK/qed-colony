# AUTO-0e3b0771bc: bounded Bool splitting for a state transition invariant

## Scope and fixed statement

This is an independent example in `Colony.Examples.BoolStateTransition`. Its
state is exactly `State` with natural-number fields `sent` and `recorded`; its
step function increments both fields when `advance = true` and returns the
input state when `advance = false`. The initial assumption is exactly
`state.sent = state.recorded`. The target is exactly
`(step state advance).sent = (step state advance).recorded`. No bounds are
present or changed. The proof attempt is `by colony` using the existing
`Colony.Tactic`; `lean/Colony/Tactic.lean` was not edited.

The adjacent false control asks `colony` to prove that the stepped `sent`
counter equals the stepped `recorded` counter plus one from the same initial
equality assumption. `fail_if_success` requires this tactic attempt to fail.

## Experiments and results

Source revision: `6d4efea988ed6a34038a64bb4c8280290cd15700`.

First attempt: after adding the state, step, and direct `by colony` theorem,
`cd lean && lake build Colony.Examples.BoolStateTransition` exited 1 with
`colony: the initial proof portfolio could not close this goal`. The Bool split
alone could not simplify projections through the named step definition.

Adjustment: added `[simp]` projection equations for the two fields of `step`.
These do not prove the invariant; they expose the step's branch equations to
the tactic's existing `simp_all` portfolio. No tactic integration or tactic
source change was made.

Final command, from repository root:

```sh
cd lean && lake build Colony.Examples.BoolStateTransition
```

Result: exit 0, build completed successfully (4 jobs). Compilation checks the
positive theorem's `by colony` attempt, and the false control compiles with
`fail_if_success`, so `colony` did not close the false target. The source also
prints this exact axiom report:

```text
'Colony.Examples.BoolStateTransition.step_preserves_counter_agreement' depends on axioms: [propext]
```

## Assurance and limits

The successful tactic attempt constructed a Lean proof term for the stated
one-step invariant, and Lean's elaborator/kernel accepted the example module
under the pinned `leanprover/lean4:v4.35.0` toolchain. The reported dependency is
`propext`; no `sorryAx`, custom axiom, or disabled kernel check is reported.
This is elaborator/kernel acceptance of this example, not exported replay,
independent-kernel acceptance, or evidence about Cardano execution. The
false-control result is tactic rejection observed through the successful
`fail_if_success` check, not a general soundness or completeness claim.
