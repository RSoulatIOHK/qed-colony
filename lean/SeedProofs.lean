import Colony
open Colony.Seed

theorem case_arithmetic_monotonicity : ∀ (x y : Nat), x ≤ y → x + 1 ≤ y + 1 := by
  colony
#print axioms case_arithmetic_monotonicity

theorem case_reverse_accumulator_length : ∀ (xs acc : List Nat), (reverseAcc xs acc).length = xs.length + acc.length := by
  colony
#print axioms case_reverse_accumulator_length

theorem case_count_accumulator_invariant : ∀ (xs : List Nat) (n : Nat), countAcc xs n = xs.length + n := by
  colony
#print axioms case_count_accumulator_invariant

theorem case_recursive_program_nonvacuity : reverseAcc [1, 2, 3] [] = [3, 2, 1] ∧ countAcc [1, 2, 3] 4 = 7 := by
  colony
#print axioms case_recursive_program_nonvacuity

theorem case_account_state_invariant : ∀ (s : Account) (reserve amount : Nat), s.balance = s.received + reserve → (deposit s amount).balance = (deposit s amount).received + reserve := by
  colony
#print axioms case_account_state_invariant

theorem case_allocated_payments_cover_sales : ∀ (priceA priceB paidA paidB : Nat), allocatedSales priceA priceB paidA paidB → priceA + priceB ≤ paidA + paidB := by
  colony
#print axioms case_allocated_payments_cover_sales

theorem case_allocated_payments_nonvacuity : allocatedSales 10 15 10 15 ∧ 10 + 15 ≤ 10 + 15 := by
  colony
#print axioms case_allocated_payments_nonvacuity

theorem case_shared_payment_attack_witness : sharedPaymentSales 10 10 10 ∧ ¬ (10 + 10 ≤ 10) := by
  colony
#print axioms case_shared_payment_attack_witness
