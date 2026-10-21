/-!
An intentionally small state-transition model for command lists.
-/

namespace Colony.Procedure

structure ListState where
  balance : Nat
  recorded : Nat
  deriving DecidableEq, Repr

inductive ListCommand where
  | record : Nat → ListCommand
  | skip : ListCommand
  deriving DecidableEq, Repr

/-- Apply one command, updating both tracked quantities together. -/
def step (state : ListState) (command : ListCommand) : ListState :=
  match command with
  | .record amount =>
      ⟨state.balance + amount, state.recorded + amount⟩
  | .skip => state

/-- Process commands in order, threading the state through the list. -/
def process (commands : List ListCommand) (state : ListState) : ListState :=
  match commands with
  | [] => state
  | command :: rest => process rest (step state command)

end Colony.Procedure
