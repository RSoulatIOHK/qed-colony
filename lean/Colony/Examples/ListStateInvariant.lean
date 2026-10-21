import Colony.Tactic
import Colony.Procedures.ListState

namespace Colony.Examples

open Colony.Procedure

/-- Equality of the two counters survives every sequence of commands. -/
theorem process_preserves_list_state_invariant
    (commands : List ListCommand) (state : ListState)
    (h : state.balance = state.recorded) :
    (process commands state).balance = (process commands state).recorded := by
  colony

/-- A deliberately false target: processing the empty list adds no offset. -/
example : ¬ (process ([] : List ListCommand) ⟨0, 0⟩).balance =
    (process ([] : List ListCommand) ⟨0, 0⟩).recorded + 1 := by
  decide

example : True := by
  fail_if_success
    (have : (process ([] : List ListCommand) ⟨0, 0⟩).balance =
        (process ([] : List ListCommand) ⟨0, 0⟩).recorded + 1 := by
      colony)
  trivial

end Colony.Examples
