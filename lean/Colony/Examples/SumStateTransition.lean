import Colony.Tactic

namespace Colony.Examples.SumStateTransition

/-- Each command selects one of two counter updates. -/
def step (count : Nat) (advance : Bool) : Sum Nat Nat :=
  if advance then .inl (count + 1) else .inr (count + 2)

@[simp] theorem step_true (count : Nat) : step count true = .inl (count + 1) := by
  simp [step]

@[simp] theorem step_false (count : Nat) : step count false = .inr (count + 2) := by
  simp [step]

/-- Either transition outcome is strictly greater than its input count. -/
theorem step_advances_count (count : Nat) (advance : Bool) :
    (match step count advance with
      | .inl value => value > count
      | .inr value => value > count) := by
  colony

/-- The constructor-specific update equations imply the transition bound. -/
theorem result_shape_advances_count (count : Nat) (result : Sum Nat Nat)
    (h : match result with
      | .inl value => value = count + 1
      | .inr value => value = count + 2) :
    (match result with
      | .inl value => value > count
      | .inr value => value > count) := by
  colony

#print axioms step_advances_count
#print axioms result_shape_advances_count

example : step 4 true = .inl 5 := by rfl
example : step 4 false = .inr 6 := by rfl

example (_result : Sum Nat Nat) : True := by
  fail_if_success
    (have : (match _result with
      | .inl next => next > 1
      | .inr next => next > 1) := by
      colony)
  trivial

example : ¬ (match (Sum.inl 0 : Sum Nat Nat) with
    | .inl next => next > 1
    | .inr next => next > 1) := by
  decide

end Colony.Examples.SumStateTransition
