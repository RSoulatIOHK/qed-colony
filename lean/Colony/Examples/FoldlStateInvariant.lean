import Colony.Tactic

namespace Colony.Examples.FoldlStateInvariant

abbrev State := Nat × Nat

/-- Add the same input to both components of the accumulator. -/
def step (state : State) (input : Nat) : State :=
  (state.1 + input, state.2 + input)

/-- Run the accumulator transition over the input list from the given state. -/
def run (inputs : List Nat) (initial : State) : State :=
  inputs.foldl step initial

/-- Equality of the accumulator components is invariant for every input list. -/
theorem run_preserves_equality (inputs : List Nat) (initial : State)
    (h : initial.1 = initial.2) :
    (run inputs initial).1 = (run inputs initial).2 := by
  fail_if_success colony
  induction inputs generalizing initial with
  | nil => simpa [run]
  | cons input inputs ih =>
      simp only [run, List.foldl_cons, step]
      exact ih (step initial input) (by simp [step, h])

/-- Nearby false control: folding cannot make the components differ by one. -/
example (inputs : List Nat) (initial : State)
    (h : initial.1 = initial.2) : True := by
  fail_if_success
    (have wrong : (run inputs initial).1 = (run inputs initial).2 + 1 := by
      colony)
  trivial

end Colony.Examples.FoldlStateInvariant
