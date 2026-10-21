import Colony.Tactic
namespace Colony.Examples

theorem nat_mul_comm_regression (a b : Nat) : a * b = b * a := by colony

-- An inhabited, nonzero instance of the unchanged target.
theorem nat_mul_comm_nonvacuity : 2 * 3 = 3 * 2 := by colony

example : True := by
  fail_if_success
    (have : ∀ a b : Nat, a * b = b * a + 1 := by colony)
  trivial

-- Refute exactly the universal claim rejected above, using a concrete witness.
theorem shifted_mul_comm_false : ¬ (∀ a b : Nat, a * b = b * a + 1) := by
  intro h
  have impossible := h 0 0
  omega

#print axioms nat_mul_comm_regression
#print axioms nat_mul_comm_nonvacuity
#print axioms shifted_mul_comm_false

end Colony.Examples
