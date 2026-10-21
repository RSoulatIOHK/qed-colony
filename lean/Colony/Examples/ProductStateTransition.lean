import Colony.Tactic

namespace Colony.Examples

/-- A transition updates both components of a pair by the same amount. -/
@[simp] def advancePair (state : Nat × Nat) : Nat × Nat :=
  match state with
  | (left, right) => (left + 1, right + 1)

/-- The difference between the counters is invariant under the transition. -/
theorem advancePair_preserves_difference (state : Nat × Nat) :
    (advancePair state).1 - (advancePair state).2 = state.1 - state.2 := by
  colony

example (state : Nat × Nat) : True := by
  fail_if_success
    (have : (advancePair state).1 = (advancePair state).1 + 1 := by
      colony)
  trivial

end Colony.Examples
