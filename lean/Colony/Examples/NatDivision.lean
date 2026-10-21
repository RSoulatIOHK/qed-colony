import Colony.Tactic

namespace Colony.Examples

theorem nat_mod_lt_succ (n d : Nat) : n % (d + 1) < d + 1 := by colony

theorem nat_div_le_self_succ (n d : Nat) : n / (d + 1) ≤ n := by colony

/-- A nearby false strengthening must not be accepted. -/
example : ¬ (0 % (0 + 1) < 0) := by
  fail_if_success (have : 0 % (0 + 1) < 0 := by colony)
  decide

#print axioms nat_mod_lt_succ
#print axioms nat_div_le_self_succ

end Colony.Examples
