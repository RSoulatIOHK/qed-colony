# AUTO-6b0b9b3bbf: `List.foldl` state-invariant probe

## Scope and source

Base revision: `713fa5e229b4d5a19afa7adce2767cb2c9f38723`; the example file
does not exist at that revision. Candidate source revision:
`bb789f5b0c450cdbe126963bdf1f0efb78d8b31a`, which adds
`lean/Colony/Examples/FoldlStateInvariant.lean` and this note.
The source-revision wording in this note was corrected in the working tree
after the candidate commit, without changing the Lean example.
No tactic implementation changes were needed. The state is a pair of natural
numbers; each input is added to both components using `List.foldl`.

## Exact procedure and target

```lean
abbrev State := Nat × Nat

def step (state : State) (input : Nat) : State :=
  (state.1 + input, state.2 + input)

def run (inputs : List Nat) (initial : State) : State :=
  inputs.foldl step initial

theorem run_preserves_equality (inputs : List Nat) (initial : State)
    (h : initial.1 = initial.2) :
    (run inputs initial).1 = (run inputs initial).2 := by
  fail_if_success colony
  induction inputs generalizing initial with
  | nil => simpa [run]
  | cons input inputs ih =>
      simp only [run, List.foldl_cons, step]
      exact ih (step initial input) (by simp [step, h])
```

The procedure, theorem statement, assumptions, and bounds are unchanged across
attempts. In a temporary copy of the example, the positive target's complete
proof body was exactly `by colony`; it failed. The candidate revision instead
checks in the displayed `fail_if_success colony` guard followed by a generic
list induction proof, so the theorem remains checked by Lean. That induction
proof is the source of the accepted theorem, not `colony`.

The nearby false control is:

```lean
example (inputs : List Nat) (initial : State)
    (h : initial.1 = initial.2) : True := by
  fail_if_success
    (have wrong : (run inputs initial).1 = (run inputs initial).2 + 1 := by
      colony)
  trivial
```

## Attempts and commands

- Earlier, `cd lean && lake env lean Colony/Examples/FoldlStateInvariant.lean`
  failed at import resolution (`unknown module prefix 'Colony'`) before the
  library was built. This was a build setup failure.
- At candidate revision `bb789f5b0c450cdbe126963bdf1f0efb78d8b31a`,
  `cd lean && lake build Colony` exited 0 on the pinned Lean 4.35.0 project.
  It replayed previously built modules and emitted unrelated linter warnings.
- A temporary copy replaced only the positive theorem's proof body with
  `by colony`. Running `lake env lean` on that copy exited 1 and reported
  `colony: the initial proof portfolio could not close this goal` at the
  positive target. The temporary copy was removed after this check.
- `cd lean && lake env lean Colony/Examples/FoldlStateInvariant.lean` on the
  candidate file exited 0. Both `fail_if_success colony` guards passed. Lean
  emitted only unused-variable warnings for the false-control binders.

## Result and assurance

This is a negative result for the current `colony` portfolio on the generic
`List.foldl` invariant. The positive theorem and false control elaborate in
the pinned Lean project. Assurance is Lean elaborator acceptance with the
ordinary kernel checking the generated proof terms. No exported replay,
independent-kernel validation, or correspondence to Cardano execution was
performed or is claimed. No `sorry`, `admit`, or axiom was introduced.
