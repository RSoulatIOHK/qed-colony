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

def weight (tree : CommandTree) : Nat :=
  match tree with
  | .empty => 0
  | .node command left right =>
      let own := match command with
        | .noop => 0
        | .tick amount => amount
      own + weight left + weight right

def execute (tree : CommandTree) (state : TreeState) : TreeState :=
  ⟨state.leftCount + weight tree, state.rightCount + weight tree⟩

end Colony.Procedure
