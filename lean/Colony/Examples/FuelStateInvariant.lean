import Colony.Tactic

namespace Colony.Examples.FuelStateInvariant

structure CounterState where
  left : Nat
  right : Nat
  deriving Repr

/-- Each recursive call consumes one unit of natural fuel and increments
both counters together. -/
def run (fuel : Nat) (state : CounterState) : CounterState :=
  match fuel with
  | 0 => state
  | fuel + 1 => run fuel ⟨state.left + 1, state.right + 1⟩

/-- Fuel recursion preserves the exact equality invariant. -/
theorem run_preserves_equality (fuel : Nat) (state : CounterState)
    (h : state.left = state.right) :
    (run fuel state).left = (run fuel state).right := by
  fail_if_success
    (have preserved : (run fuel state).left = (run fuel state).right := by
      colony)
  induction fuel generalizing state with
  | zero => simpa [run] using h
  | succ fuel ih =>
      simpa [run] using
        (ih ⟨state.left + 1, state.right + 1⟩ (by
          change state.left + 1 = state.right + 1
          omega))

/-- A false nearby target is not proved by `colony`. -/
example (fuel : Nat) (state : CounterState)
    (h : state.left = state.right) : True := by
  fail_if_success
    (have impossible : (run fuel state).left = (run fuel state).right + 1 := by
      colony)
  trivial

end Colony.Examples.FuelStateInvariant
