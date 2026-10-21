import Colony.Tactic

namespace Colony.Examples

theorem option_nat_positive (choice : Option Nat) (n : Nat) :
    (match choice with
      | none => n + 2
      | some value => n + value + 1) > n := by
  colony

/-- The irrelevant first option fails; colony restores the goal and tries the next one. -/
theorem option_after_failed_candidate
    (irrelevant choice : Option Nat) (n : Nat) :
    (match choice with
      | none => n + 2
      | some value => n + value + 1) > n := by
  colony

example (choice : Option Nat) : True := by
  fail_if_success
    (have : (match choice with
      | none => 0
      | some _ => 1) = 2 := by
      colony)
  trivial

end Colony.Examples
