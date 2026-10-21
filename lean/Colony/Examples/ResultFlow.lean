import Colony.Tactic

namespace Colony.Examples

/-- A successful result adds the same amount to both counters. -/
@[simp] def applyResult (state : Nat × Nat) (result : Except String Nat) : Nat × Nat :=
  match result with
  | .ok amount => (state.1 + amount, state.2 + amount)
  | .error _ => state

/-- Original statement and assumptions: `state : Nat × Nat`,
`result : Except String Nat`, and `state.1 = state.2`; both counters
remain equal after the transition. -/
theorem successful_result_updates_counters_consistently
    (state : Nat × Nat) (result : Except String Nat)
    (h : state.1 = state.2) :
    (applyResult state result).1 = (applyResult state result).2 := by
  colony

/-- Failure returns exactly the input state. -/
theorem failed_result_leaves_state_unchanged
    (state : Nat × Nat) (message : String) :
    applyResult state (.error message) = state := by
  rfl

theorem except_after_failed_candidate (irrelevant choice : Except String Nat)
    (n : Nat) :
    (applyResult (n, n) choice).1 = (applyResult (n, n) choice).2 := by
  colony

example (state : Nat × Nat) (result : Except String Nat) : True := by
  fail_if_success
    (have : (applyResult state result).1 = (applyResult state result).1 + 1 := by
      colony)
  trivial

end Colony.Examples
