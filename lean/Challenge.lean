import Colony.Seeds

/-!
Reviewed seed challenge: the exact eight positive statements from seed-v1.json.
Ordinary bundled tactics fill the proofs so this specification contains no proof
holes. Comparator uses the prescribed statements and their definition closure;
these challenge proof bodies are not the candidate solution.
-/
open Colony.Seed

theorem case_arithmetic_monotonicity : ∀ (x y : Nat), x ≤ y → x + 1 ≤ y + 1 := by
  omega

theorem case_reverse_accumulator_length : ∀ (xs acc : List Nat), (reverseAcc xs acc).length = xs.length + acc.length := by
  intro xs acc
  induction xs generalizing acc <;> simp_all <;> omega

theorem case_count_accumulator_invariant : ∀ (xs : List Nat) (n : Nat), countAcc xs n = xs.length + n := by
  intro xs n
  induction xs generalizing n <;> simp_all <;> omega

theorem case_recursive_program_nonvacuity : reverseAcc [1, 2, 3] [] = [3, 2, 1] ∧ countAcc [1, 2, 3] 4 = 7 := by
  decide

theorem case_account_state_invariant : ∀ (s : Account) (reserve amount : Nat), s.balance = s.received + reserve → (deposit s amount).balance = (deposit s amount).received + reserve := by
  simp_all
  omega

theorem case_allocated_payments_cover_sales : ∀ (priceA priceB paidA paidB : Nat), allocatedSales priceA priceB paidA paidB → priceA + priceB ≤ paidA + paidB := by
  simp_all
  omega

theorem case_allocated_payments_nonvacuity : allocatedSales 10 15 10 15 ∧ 10 + 15 ≤ 10 + 15 := by
  simp

theorem case_shared_payment_attack_witness : sharedPaymentSales 10 10 10 ∧ ¬ (10 + 10 ≤ 10) := by
  simp
