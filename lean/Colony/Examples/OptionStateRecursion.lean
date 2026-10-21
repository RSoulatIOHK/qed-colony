import Colony.Tactic

namespace Colony.Examples

/-- A command either fails or advances the state by one. -/
def optionStep (state : Nat) (command : Bool) : Option Nat :=
  if command then some (state + 1) else none

/-- Execute exactly two commands, stopping if either command fails. -/
def runTwo (state : Nat) (first second : Bool) : Option Nat := do
  let afterFirst ← optionStep state first
  optionStep afterFirst second

/-- Every successful two-command run advances the state at least twice. -/
theorem runTwo_success_advances
    (state finalState : Nat) (first second : Bool)
    (h : runTwo state first second = some finalState) :
    state + 2 ≤ finalState := by
  fail_if_success colony
  cases first <;> cases second <;>
    simp [runTwo, optionStep] at h ⊢ <;> omega

example (state finalState : Nat) (first second : Bool)
    (_h : runTwo state first second = some finalState) : True := by
  fail_if_success
    (have : state + 3 ≤ finalState := by
      colony)
  trivial

end Colony.Examples
