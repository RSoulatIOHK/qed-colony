import Colony.Tactic
import Colony.Procedures.ListState

namespace Colony.Examples

open Colony.Procedure

/-- One command preserves equality of the two counters. -/
theorem step_preserves_list_state_invariant
    (state : ListState) (command : ListCommand)
    (h : state.balance = state.recorded) :
    (step state command).balance = (step state command).recorded := by
  colony

/-- The invariant survives two adjacent commands, composed in execution order. -/
theorem adjacent_steps_preserve_list_state_invariant
    (state : ListState) (first second : ListCommand)
    (h : state.balance = state.recorded) :
    (step (step state first) second).balance =
      (step (step state first) second).recorded := by
  fail_if_success
    (have : (step (step state first) second).balance =
        (step (step state first) second).recorded := by
      colony)
  cases first <;> cases second <;> simp [step] <;> omega

example (_state : ListState) (_first _second : ListCommand)
    (_h : _state.balance = _state.recorded) : True := by
  fail_if_success
    (have : (step (step _state _first) _second).balance =
        (step (step _state _first) _second).recorded + 1 := by
      colony)
  trivial

example (state : ListState) (command : ListCommand) : True := by
  fail_if_success
    (have : (step state command).balance =
        (step state command).recorded + 1 := by
      colony)
  trivial

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
