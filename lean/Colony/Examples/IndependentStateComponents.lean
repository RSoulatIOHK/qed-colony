import Colony.Tactic

namespace Colony.Examples.IndependentStateComponents

structure State where
  balance : Nat
  recorded : Nat
  deriving DecidableEq, Repr

inductive Command where
  | addBalance (amount : Nat)
  | addRecorded (amount : Nat)
  | skip
  deriving DecidableEq, Repr

/-- A bounded sequence contains at most `bound` commands. -/
def Bounded (bound : Nat) (commands : List Command) : Prop :=
  commands.length ≤ bound

/-- Each update command changes exactly one field. -/
def step (state : State) (command : Command) : State :=
  match command with
  | .addBalance amount => ⟨state.balance + amount, state.recorded⟩
  | .addRecorded amount => ⟨state.balance, state.recorded + amount⟩
  | .skip => state

/-- Execute a sequence in order. -/
def run (commands : List Command) (state : State) : State :=
  match commands with
  | [] => state
  | command :: rest => run rest (step state command)

theorem step_balance_monotone (state : State) (command : Command) :
    state.balance ≤ (step state command).balance := by
  cases command <;> simp [step] <;> omega

/-- Any bounded command sequence preserves the lower bound on `balance`.
The bound controls sequence length; no restriction is placed on command amounts.
-/
theorem bounded_run_balance_monotone (bound : Nat) (commands : List Command)
    (state : State) (_hbound : Bounded bound commands) :
    state.balance ≤ (run commands state).balance := by
  induction commands generalizing state with
  | nil => exact Nat.le_refl _
  | cons command rest ih =>
      simp only [run]
      exact Nat.le_trans (step_balance_monotone state command)
        (ih (step state command) (by
          change rest.length + 1 ≤ bound at _hbound
          change rest.length ≤ bound
          omega))

example : Bounded 2 [.addBalance 1, .addRecorded 2] := by
  simp [Bounded]

example : (run [.addBalance 1, .addRecorded 2] ⟨3, 3⟩).balance = 4 := by
  rfl

/-- `colony` does not currently synthesize the structural induction for this
user-defined state and run wrapper. This guards the observed limitation.
-/
example (bound : Nat) (commands : List Command) (state : State)
    (_hbound : Bounded bound commands) : True := by
  fail_if_success
    (have : state.balance ≤ (run commands state).balance := by colony)
  trivial

/-- The tempting preservation claim that `recorded` never changes is false. -/
example : ¬ (∀ state : State, ∀ commands : List Command,
    (run commands state).recorded = state.recorded) := by
  intro h
  have hbad := h ⟨0, 0⟩ [.addRecorded 1]
  simp [run, step] at hbad

end Colony.Examples.IndependentStateComponents
