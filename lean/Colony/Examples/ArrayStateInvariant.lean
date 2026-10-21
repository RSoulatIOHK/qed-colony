import Colony.Tactic

namespace Colony.Examples

/-- Update one array slot when it is in bounds. -/
@[simp] def updateArrayState (state : Array Nat) (index value : Nat) : Array Nat :=
  state.setIfInBounds index value

/-- Updating an array slot preserves the array's size. -/
theorem updateArrayState_preserves_size
    (state : Array Nat) (updated value : Nat) :
    (updateArrayState state updated value).size = state.size := by
  colony

example (state : Array Nat) (updated value : Nat) : True := by
  fail_if_success
    (have : (updateArrayState state updated value).size = state.size + 1 := by
      colony)
  trivial

end Colony.Examples
