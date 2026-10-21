import Colony.Tactic

namespace Colony.Examples.BoolStateTransition

structure State where
  sent : Nat
  recorded : Nat
  deriving Repr

structure Command where
  advance : Bool
  deriving Repr

/-- A true command advances both counters; a false command leaves them alone. -/
def step (state : State) (command : Command) : State :=
  if command.advance then
    ⟨state.sent + 1, state.recorded + 1⟩
  else
    state

example : step ⟨0, 0⟩ ⟨true⟩ = ⟨1, 1⟩ := by rfl
example : step ⟨0, 0⟩ ⟨false⟩ = ⟨0, 0⟩ := by rfl

@[simp] theorem step_sent (state : State) (command : Command) :
    (step state command).sent =
      if command.advance then state.sent + 1 else state.sent := by
  cases command with
  | mk advance => cases advance <;> rfl

@[simp] theorem step_recorded (state : State) (command : Command) :
    (step state command).recorded =
      if command.advance then state.recorded + 1 else state.recorded := by
  cases command with
  | mk advance => cases advance <;> rfl

/-- The counters remain equal after one command, assuming they started equal. -/
theorem step_preserves_counter_agreement
    (state : State) (command : Command)
    (h : state.sent = state.recorded) :
    (step state command).sent = (step state command).recorded := by
  colony

#print axioms step_preserves_counter_agreement

example (_state : State) (_command : Command)
    (_h : _state.sent = _state.recorded) : True := by
  fail_if_success
    (have : (step _state _command).sent =
        (step _state _command).recorded + 1 := by
      colony)
  trivial

example : (step ⟨0, 0⟩ ⟨false⟩).sent ≠
    (step ⟨0, 0⟩ ⟨false⟩).recorded + 1 := by decide

end Colony.Examples.BoolStateTransition
