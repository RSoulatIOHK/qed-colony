# AUTO-6b0b9b3bbf: `List.foldl` state-invariant probe

## Scope and source

Base/source revision: `713fa5e229b4d5a19afa7adce2767cb2c9f38723`.
The probe is implemented in `lean/Colony/Examples/FoldlStateInvariant.lean`.
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
attempts. The positive tactic probe was exactly `by colony` on this target; it
failed. The checked-in proof catches that failure and supplies a generic list
induction proof so the theorem remains checked by Lean.

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

- `cd lean && lake env lean Colony/Examples/FoldlStateInvariant.lean` before
  building the library failed at import resolution (`unknown module prefix
  'Colony'`). This was a build setup issue.
- `cd lean && lake build Colony` built the project library (Lean 4.35.0).
- Retrying `cd lean && lake env lean
  Colony/Examples/FoldlStateInvariant.lean` with the target body exactly
  `by colony` failed at the target with `colony: the initial proof portfolio
  could not close this goal` (exit 1). Thus the exact `by colony` positive
  attempt did not solve this foldl case.
- With the induction proof and `fail_if_success colony` guard in place,
  `cd lean && lake env lean Colony/Examples/FoldlStateInvariant.lean` exited
  0. The false-control guard also passed; if `colony` had proved its false
  proposition, `fail_if_success` would have failed the file. Lean emitted only
  unused-variable warnings for control-example binders.

## Result and assurance

This is a negative result for the current `colony` portfolio on the generic
`List.foldl` invariant. The positive theorem and false control elaborate in
the pinned Lean project. Assurance is Lean elaborator acceptance with the
ordinary kernel checking the generated proof terms. No exported replay,
independent-kernel validation, or correspondence to Cardano execution was
performed or is claimed. No `sorry`, `admit`, or axiom was introduced.
