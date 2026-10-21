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

end Colony.Examples
