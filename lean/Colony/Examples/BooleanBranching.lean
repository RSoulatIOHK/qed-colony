import Colony.Tactic

namespace Colony.Examples

theorem conditional_positive (flag : Bool) (n : Nat) :
    (if flag then n + 1 else n + 2) > n := by
  colony

theorem arithmetic_regression (a b : Nat) (h : a ≤ b) :
    a + 3 ≤ b + 3 := by
  colony

example (flag : Bool) : True := by
  fail_if_success (have : False := by colony)
  trivial

end Colony.Examples
