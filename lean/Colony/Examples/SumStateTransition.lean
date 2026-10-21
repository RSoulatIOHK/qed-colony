import Colony.Tactic

namespace Colony.Examples.SumStateTransition

/-- Each command selects one of two counter updates. -/
def step (count : Nat) (advance : Bool) : Sum Nat Nat :=
  if advance then .inl (count + 1) else .inr (count + 2)

@[simp] theorem step_true (count : Nat) : step count true = .inl (count + 1) := by
  simp [step]

@[simp] theorem step_false (count : Nat) : step count false = .inr (count + 2) := by
  simp [step]

/-- Both outcomes of the transition advance the count. -/
theorem payload_successor_exceeds_itself (result : Sum Nat Nat) :
    (match result with
      | .inl value => value + 1 > value
      | .inr value => value + 1 > value) := by
  colony

#print axioms payload_successor_exceeds_itself

/-- In particular, every result produced by one transition has the invariant. -/
theorem step_preserves_payload_invariant (count : Nat) (advance : Bool) :
    (match step count advance with
      | .inl value => value + 1 > value
      | .inr value => value + 1 > value) := by
  exact payload_successor_exceeds_itself (step count advance)

example : step 4 true = .inl 5 := by rfl
example : step 4 false = .inr 6 := by rfl

example (_result : Sum Nat Nat) : True := by
  fail_if_success
    (have : (match result with
      | .inl next => next > 1
      | .inr next => next > 1) := by
      colony)
  trivial

end Colony.Examples.SumStateTransition
