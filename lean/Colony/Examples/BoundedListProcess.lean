import Colony.Tactic
import Colony.Procedures.ListState

namespace Colony.Examples

open Colony.Procedure

/-- The tactic's single-candidate recursive fallback proves the invariant for
an arbitrary command list, without changing the target or its assumption. -/
theorem bounded_process_preserves_list_state_invariant
    (commands : List ListCommand) (state : ListState)
    (h : state.balance = state.recorded) :
    (process commands state).balance = (process commands state).recorded := by
  colony

/-- A concrete one-command counterexample to the false offset property. -/
example : ¬ (process [ListCommand.record 1] ⟨0, 0⟩).balance =
    (process [ListCommand.record 1] ⟨0, 0⟩).recorded + 1 := by
  decide

example : True := by
  fail_if_success
    (have : (process [ListCommand.record 1] ⟨0, 0⟩).balance =
        (process [ListCommand.record 1] ⟨0, 0⟩).recorded + 1 := by
      colony)
  trivial

end Colony.Examples
