import Colony.Tactic
namespace Colony.Examples

theorem nat_mul_comm_regression (a b : Nat) : a * b = b * a := by colony

example : True := by
  fail_if_success
    (have : ∀ a b : Nat, a * b = b * a + 1 := by colony)
  trivial

end Colony.Examples
