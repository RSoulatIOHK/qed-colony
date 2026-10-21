import Colony.Tactic
import Colony.Procedures.ListState

namespace Colony.Examples

open Colony.Procedure

set_option trace.Colony.listProcess true

/-- A record and a skip follow an arbitrary command list. -/
theorem extended_process_preserves_list_state_invariant
    (commands : List ListCommand) (state : ListState)
    (h : state.balance = state.recorded) :
    (step (step (process commands state) (ListCommand.record 1)) ListCommand.skip).balance =
      (step (step (process commands state) (ListCommand.record 1)) ListCommand.skip).recorded := by
  colony

/-- A concrete one-command counterexample to the false offset property. -/
example : ¬ (process [ListCommand.record 1] ⟨0, 0⟩).balance =
    (process [ListCommand.record 1] ⟨0, 0⟩).recorded + 1 := by
  decide

example : True := by
  fail_if_success
    (have : ∀ (commands : List ListCommand) (state : ListState),
        (process commands state).balance = (process commands state).recorded + 1 := by
      colony)
  trivial

/-- The command-list path must not try induction on `amount` after it fails. -/
example : True := by
  fail_if_success
    (have : ∀ (commands : List ListCommand) (state : ListState) (amount : Nat),
        (process commands state).balance = amount := by
      colony)
  trivial

/-- Two command-list locals are deliberately outside the one-candidate bound. -/
example : True := by
  fail_if_success
    (have : ∀ (left right : List ListCommand) (state : ListState),
        (process (left ++ right) state).balance =
          (process (left ++ right) state).recorded := by
      colony)
  trivial

#print axioms extended_process_preserves_list_state_invariant

end Colony.Examples
