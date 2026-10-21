import Colony.Tactic

namespace Colony.Examples

theorem conditional_positive (flag : Bool) (n : Nat) :
    (if flag then n + 1 else n + 2) > n := by
  colony

theorem conditional_after_failed_candidate (other flag : Bool) (n : Nat) :
    (if flag then n + 1 else n + 2) > n ∧ other = other := by
  colony

theorem arithmetic_regression (a b : Nat) (h : a ≤ b) :
    a + 3 ≤ b + 3 := by
  colony

example (_flag : Bool) : True := by
  fail_if_success (have : (if _flag then 0 else 1) = 2 := by colony)
  trivial

end Colony.Examples
