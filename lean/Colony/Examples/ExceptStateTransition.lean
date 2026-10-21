import Colony.Tactic

namespace Colony.Examples.ExceptStateTransition

inductive Failure where
  | rejected
  | unavailable
  deriving Repr, DecidableEq

abbrev Input := Except Failure Nat

/-- Errors advance the state by two; successful inputs add their value and one. -/
def transition (state : Nat) (input : Input) : Nat :=
  match input with
  | .error _ => state + 2
  | .ok value => state + value + 1

/-- After exposing the transition result, colony splits the `Except` input once. -/
theorem transition_advances (input : Input) (state : Nat) :
    transition state input > state := by
  simp only [transition]
  colony

/-- The stronger bound is false for a successful input of zero. -/
example : ¬ (∀ input : Input, ∀ state : Nat,
    transition state input > state + 2) := by
  intro h
  have h0 := h (.ok 0) 0
  simp [transition] at h0

example (_input : Input) (_state : Nat) : True := by
  fail_if_success
    (have : transition _state _input > _state + 2 := by
      simp only [transition]
      colony)
  trivial

end Colony.Examples.ExceptStateTransition

#print axioms Colony.Examples.ExceptStateTransition.transition_advances
