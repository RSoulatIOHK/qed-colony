# AUTO-0e3b0771bc: bounded Bool splitting for a state transition invariant

## Scope and acceptance

This independent example fixes `State` as natural-number fields `sent` and
`recorded`, and `Command` as a structure with an `advance : Bool` field.
`step state command` increments both fields when `command.advance` is true and
otherwise returns `state`. The only initial assumption for the positive theorem
is `state.sent = state.recorded`. The exact target is
`(step state command).sent = (step state command).recorded` after one step.
There are no bounds. The positive proof attempt is exactly `by colony` with the
existing tactic. An adjacent `fail_if_success` guards the false target that the
stepped `sent` field equals the stepped `recorded` field plus one. Concrete
true and false command examples exercise both branches, and a concrete false
command refutes the control target.

Acceptance was a compiling positive theorem, a compiling guarded rejection of
the false target, and an axiom report, without changes to the tactic or to
evaluation, benchmark, policy, or challenge files.

## Source identity and experiments

Base revision: `6d4efea988ed6a34038a64bb4c8280290cd15700` (before this
example existed). Prior reviewed revision: `cbaf5368651525d626511eea08665fecb07d2ed4`.
That revision has a standalone `advance : Bool` parameter; the SHA-256 of its
example file is `1ce58dce35937ba0afb52d17fba350c4464b01759c66b5837f48e9ba9daba66b`.
Its report records an earlier uncommitted failed build before projection lemmas
were added. No content hash for that first failed source was retained, so its
exact source identity cannot be established from the record.

For the command-field revision, the first `cd lean && lake build
Colony.Examples.BoolStateTransition` exited 1. The two projection lemmas used
`cases command.advance <;> rfl`. Lean reported that `(step state command).sent`
and `(step state command).recorded` were not definitionally equal to their
respective branch expressions after the field split. The failed build also
printed `[propext, sorryAx]` for the positive theorem because its source had
errors; that output is **not** an accepted proof or the final axiom report.
Splitting the `Command` constructor before its Bool field fixed the projection
lemmas, using `cases command with | mk advance => cases advance <;> rfl`.

Final tested source is the uncommitted worktree based on `cbaf536` with
SHA-256 `829bff3bc9b2d0f2d195b46226280885ba4f992ca357adeab7b8361001b79cd6`
for `lean/Colony/Examples/BoolStateTransition.lean`. The unchanged tactic file
has SHA-256 `d193f91238ab9d7a49856df2430588b56246fafd73f8036015b0facf47002a88`.
These hashes identify the source used for the final build and axiom output;
the base revision alone does not.

Final command, from repository root:

```sh
cd lean && lake build Colony.Examples.BoolStateTransition
```

Result: exit 0, `Build completed successfully (4 jobs)` under the pinned
`leanprover/lean4:v4.35.0` toolchain. The source's `#print axioms` output was:

```text
'Colony.Examples.BoolStateTransition.step_preserves_counter_agreement' depends on axioms: [propext]
```

## Assurance and limits

The positive `by colony` theorem and the two example-level projection lemmas
were accepted by Lean's elaborator/kernel. The projection lemmas expose the
step branches to simplification; the successful build does not establish that
`colony` itself split `command.advance`. The concrete branch examples and
false counterexample are additional example-level proofs. The guarded
`fail_if_success` establishes that `colony` did not close the stated false
target in this context. The positive theorem's reported axiom dependency is
`propext`, with no `sorryAx` in the successful build. This is Lean
elaborator/kernel acceptance of this example, not exported replay,
independent-kernel acceptance, or correspondence to Cardano execution.
