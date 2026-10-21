/-! A compact binary command tree and its state transition model. -/

namespace Colony.Procedure

structure TreeState where
  leftCount : Nat
  rightCount : Nat
  deriving DecidableEq, Repr

inductive TreeCommand where
  | noop
  | tick : Nat → TreeCommand
  deriving DecidableEq, Repr

inductive CommandTree where
  | empty
  | node : TreeCommand → CommandTree → CommandTree → CommandTree
  deriving DecidableEq, Repr

def applyCommand (state : TreeState) (command : TreeCommand) : TreeState :=
  match command with
  | .noop => state
  | .tick amount => ⟨state.leftCount + amount, state.rightCount + amount⟩

def execute (tree : CommandTree) (state : TreeState) : TreeState :=
  match tree with
  | .empty => state
  | .node command left right =>
      execute right (execute left (applyCommand state command))

end Colony.Procedure
