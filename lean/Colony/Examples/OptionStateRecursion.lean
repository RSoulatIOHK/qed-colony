import Colony.Tactic

namespace Colony.Examples

/-- A command either fails or advances the state by one. -/
def optionStep (state : Nat) (command : Bool) : Option Nat :=
  if command then some (state + 1) else none

/-- Execute at most `fuel` commands, stopping on failure or missing input. -/
def runBounded : Nat → Nat → List Bool → Option Nat
  | 0, state, _ => some state
  | fuel + 1, state, commands =>
      match commands with
      | [] => none
      | command :: remaining => do
          let next ← optionStep state command
          runBounded fuel next remaining

/-- Execute exactly two commands with a fixed semantic depth bound of two. -/
def runTwo (state : Nat) (first second : Bool) : Option Nat :=
  runBounded 2 state [first, second]

theorem runTwo_original_semantics (state : Nat) (first second : Bool) :
    runTwo state first second = (do
      let afterFirst ← optionStep state first
      optionStep afterFirst second) := by
  cases first <;> cases second <;>
    simp [runTwo, runBounded, optionStep]

/-- Every successful two-command run advances the state at least twice. -/
theorem runTwo_success_advances
    (state finalState : Nat) (first second : Bool)
    (h : runTwo state first second = some finalState) :
    state + 2 ≤ finalState := by
  fail_if_success colony
  cases first <;> cases second <;>
    simp [runTwo, runBounded, optionStep] at h ⊢ <;> omega

/-- Success is reachable, so the invariant is not vacuous. -/
example : runTwo 0 true true = some 2 := by
  decide

/-- This nearby stronger invariant is false on a successful execution. -/
example : ¬ (∀ state finalState first second,
    runTwo state first second = some finalState →
    state + 3 ≤ finalState) := by
  intro h
  have hRun : runTwo 0 true true = some 2 := by decide
  have hFalse := h 0 2 true true hRun
  omega

example (state finalState : Nat) (first second : Bool)
    (_h : runTwo state first second = some finalState) : True := by
  fail_if_success
    (have : state + 3 ≤ finalState := by
      colony)
  trivial

end Colony.Examples
