import Colony.Tactic
import Colony.Procedures.TreeState

namespace Colony.Examples

open Colony.Procedure

/-- Executing a binary command tree preserves equality of both state counters. -/
theorem execute_preserves_tree_state_invariant
    (tree : CommandTree) (state : TreeState)
    (h : state.leftCount = state.rightCount) :
    (execute tree state).leftCount = (execute tree state).rightCount := by
  colony

example (tree : CommandTree) (state : TreeState)
    (h : state.leftCount = state.rightCount) : True := by
  fail_if_success
    (have : (execute tree state).leftCount =
        (execute tree state).rightCount + 1 := by
      colony)
  trivial

/-- Root and both children execute, so the invariant is not just an empty-tree case. -/
example : execute (.node (.tick 2)
    (.node (.tick 3) .empty .empty)
    (.node (.tick 5) .empty .empty)) ⟨7, 7⟩ = ⟨17, 17⟩ := by
  rfl

/-- The precondition is inhabited, and execution does not repair unequal counters. -/
example : (TreeState.mk 7 7).leftCount = (TreeState.mk 7 7).rightCount := by
  rfl

example : (execute .empty ⟨0, 1⟩).leftCount ≠
    (execute .empty ⟨0, 1⟩).rightCount := by
  decide

/-- A kernel-checked counterexample to the deliberately false offset target. -/
example : (execute .empty ⟨0, 0⟩).leftCount ≠
    (execute .empty ⟨0, 0⟩).rightCount + 1 := by
  decide

end Colony.Examples
