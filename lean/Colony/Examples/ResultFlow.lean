import Colony.Tactic

namespace Colony.Examples

/-- A successful result adds the same amount to both counters. -/
@[simp] def applyResult (state : Nat × Nat) (result : Except String Nat) : Nat × Nat :=
  match result with
  | .ok amount => (state.1 + amount, state.2 + amount)
  | .error _ => state

/-- Original difference statement: arbitrary `state : Nat × Nat` and
`result : Except String Nat`, with no equality assumption on the counters.
Success preserves natural subtraction; failure returns the input state. -/
theorem result_preserves_counter_difference
    (state : Nat × Nat) (result : Except String Nat) :
    (applyResult state result).1 - (applyResult state result).2 =
      state.1 - state.2 := by
  colony

/-- Statement and assumptions of the first committed positive theorem:
`state : Nat × Nat`,
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

example : applyResult (2, 3) (.ok 4) = (6, 7) := by
  decide

/-- The explicit first-candidate attempt fails. `colony` must restore that
candidate and split `choice` to prove this unchanged target. -/
theorem except_after_failed_candidate (irrelevant choice : Except String Nat)
    (n : Nat) :
    (applyResult (n, n) choice).1 = (applyResult (n, n) choice).2 := by
  fail_if_success
    (solve | cases irrelevant <;> (first
      | (solve | simp_all <;> omega)
      | (solve | simp_all <;> decide)
      | (solve | omega)))
  colony

-- The error branch closes, but the ok branch is false: partial success must
-- not be reported as success or discard the remaining constructor obligation.
example (result : Except String Nat) : True := by
  fail_if_success
    (have : (match result with
      | .error _ => True
      | .ok _ => False) := by colony)
  trivial

/-- This true target needs two constructor splits. Keep it outside the bounded
fallback and prove it explicitly after checking that `colony` fails. -/
theorem two_results_need_two_splits (first second : Except String Nat) :
    (match first with | .error _ => 0 | .ok _ => 1) +
      (match second with | .error _ => 0 | .ok _ => 1) ≤ (2 : Nat) := by
  fail_if_success colony
  cases first <;> cases second <;> simp

-- A concrete success and failure witness establish that the transition is
-- inhabited and the false offset target below has a counterexample.
example : applyResult (2, 3) (.error "failed") = (2, 3) := by
  decide

example : ¬ ((applyResult (2, 3) (.ok 4)).1 =
    (applyResult (2, 3) (.ok 4)).1 + 1) := by
  decide

example (state : Nat × Nat) (result : Except String Nat) : True := by
  fail_if_success
    (have : (applyResult state result).1 = (applyResult state result).1 + 1 := by
      colony)
  trivial

end Colony.Examples
