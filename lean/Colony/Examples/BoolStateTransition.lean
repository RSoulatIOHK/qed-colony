import Colony.Tactic

namespace Colony.Examples.BoolStateTransition

structure State where
  sent : Nat
  recorded : Nat
  deriving Repr

/-- A true command advances both counters; a false command leaves them alone. -/
def step (state : State) (advance : Bool) : State :=
  if advance then
    ⟨state.sent + 1, state.recorded + 1⟩
  else
    state

@[simp] theorem step_sent (state : State) (advance : Bool) :
    (step state advance).sent = if advance then state.sent + 1 else state.sent := by
  cases advance <;> rfl

@[simp] theorem step_recorded (state : State) (advance : Bool) :
    (step state advance).recorded =
      if advance then state.recorded + 1 else state.recorded := by
  cases advance <;> rfl

/-- The counters remain equal after one command, assuming they started equal. -/
theorem step_preserves_counter_agreement
    (state : State) (advance : Bool)
    (h : state.sent = state.recorded) :
    (step state advance).sent = (step state advance).recorded := by
  colony

#print axioms step_preserves_counter_agreement

example (_state : State) (_advance : Bool)
    (_h : _state.sent = _state.recorded) : True := by
  fail_if_success
    (have : (step _state _advance).sent =
        (step _state _advance).recorded + 1 := by
      colony)
  trivial

end Colony.Examples.BoolStateTransition
