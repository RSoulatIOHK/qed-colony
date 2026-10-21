import Colony

open Colony.Procedure

-- The pre-induction portfolio cannot prove this goal; the tree branch must.
example (tree : CommandTree) (state : TreeState)
    (h : state.leftCount = state.rightCount) :
    (execute tree state).leftCount = (execute tree state).rightCount := by
  fail_if_success (solve | omega)
  fail_if_success (solve | simp_all <;> omega)
  fail_if_success (solve | decide)
  -- Simplification alone cannot instantiate both recursive hypotheses.
  fail_if_success
    (solve | induction tree generalizing state <;>
      (simp_all [execute, applyCommand] <;> omega))
  colony

-- The tree candidate fails, restores the goal, and the later bridge closes it.
theorem tree_candidate_rollback (_tree : CommandTree) (xs acc : List Nat) :
    Colony.Seed.reverseAcc xs acc = xs.reverse ++ acc := by
  fail_if_success (solve | omega)
  fail_if_success (solve | simp_all <;> omega)
  fail_if_success (solve | decide)
  colony

-- Two eligible locals must disable this bounded induction branch.
example (tree _other : CommandTree) (state : TreeState)
    (h : state.leftCount = state.rightCount) :
    (execute tree state).leftCount = (execute tree state).rightCount := by
  fail_if_success colony
  exact Colony.Examples.execute_preserves_tree_state_invariant tree state h

-- A known boundary: the fixed IH applications cannot discharge an additional
-- generalized hypothesis about the intermediate state. Failure is recoverable.
example (tree : CommandTree) (state : TreeState) (n : Nat)
    (hn : n = state.leftCount) (h : state.leftCount = state.rightCount) :
    (execute tree state).leftCount = (execute tree state).rightCount := by
  fail_if_success colony
  exact Colony.Examples.execute_preserves_tree_state_invariant tree state h

#print axioms Colony.Examples.execute_preserves_tree_state_invariant
#print axioms tree_candidate_rollback
