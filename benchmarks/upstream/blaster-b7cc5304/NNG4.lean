
namespace BlasterBenchmarks.NNG4
abbrev ℕ := Nat

section Addition
open Nat
  theorem zero_add : ∀ (n : ℕ), 0 + n = n := by sorry
  theorem succ_add (a b : ℕ) : succ a + b = succ (a + b)  := by sorry
  theorem add_comm (a b : ℕ) : a + b = b + a := by sorry
  theorem add_assoc (a b c : ℕ) : a + b + c = a + (b + c) := by sorry
  theorem add_right_comm (a b c : ℕ) : a + b + c = a + c + b := by sorry
end Addition

section AdvAddition
  theorem add_right_cancel (a b n : ℕ) : a + n = b + n → a = b := by sorry
  theorem add_left_cancel (a b n : ℕ) : n + a = n + b → a = b := by sorry
  theorem add_left_eq_self (x y : ℕ) : x + y = y → x = 0 := by sorry
  theorem add_right_eq_self (x y : ℕ) : x + y = x → y = 0 := by sorry
  theorem add_right_eq_zero (a b : ℕ) : a + b = 0 → a = 0 := by sorry
  theorem add_left_eq_zero (a b : ℕ) : a + b = 0 → b = 0 := by sorry
end AdvAddition

section AdvMultiplication
open Nat
  theorem mul_le_mul_right (a b t : ℕ) (h : a ≤ b) : a * t ≤ b * t := by sorry
  theorem mul_left_ne_zero (a b : ℕ) (h : a * b ≠ 0) : b ≠ 0 := by sorry
  theorem eq_succ_of_ne_zero (a : ℕ) (ha : a ≠ 0) : ∃ n, a = succ n := by sorry
  theorem one_le_of_ne_zero (a : ℕ) (ha : a ≠ 0) : 1 ≤ a := by sorry
  theorem le_mul_right (a b : ℕ) (h : a * b ≠ 0) : a ≤ a * b := by sorry
  theorem mul_right_eq_one (x y : ℕ) (h : x * y = 1) : x = 1 := by sorry
  theorem mul_ne_zero (a b : ℕ) (ha : a ≠ 0) (hb : b ≠ 0) : a * b ≠ 0 := by sorry
  theorem mul_eq_zero (a b : ℕ) (h : a * b = 0) : a = 0 ∨ b = 0 := by sorry
  theorem mul_left_cancel (a b c : ℕ) (ha : a ≠ 0) (h : a * b = a * c) : b = c := by sorry
  theorem mul_right_eq_self (a b : ℕ) (ha : a ≠ 0) (h : a * b = a) : b = 1 := by sorry
end AdvMultiplication

section Algorithm
open Nat
  theorem add_left_comm (a b c : ℕ) : a + (b + c) = b + (a + c) := by sorry
  theorem add_algo1 (a b c d : ℕ) : a + b + (c + d) = a + c + d + b := by sorry
  theorem add_algo2 (a b c d e f g h : ℕ) :
      (d + f) + (h + (a + c)) + (g + e + b) = a + b + c + d + e + f + g + h := by sorry
  theorem add_algo3 (a b c d e f g h : ℕ) :
      (d + f) + (h + (a + c)) + (g + e + b) = a + b + c + d + e + f + g + h := by sorry
  theorem pred05 (a b : ℕ) (h : succ a = succ b) : a = b := by sorry
  theorem succ_ne_zero (a : ℕ) : succ a ≠ 0 := by sorry
  theorem succ_ne_succ (m n : ℕ) (h : m ≠ n) : succ m ≠ succ n := by sorry
  theorem decide : (20 : ℕ) + 20 = 40 := by decide +native
  theorem decide2 : (2 : ℕ) + 2 ≠ 5 := by sorry
end Algorithm

section Implication
open Nat
  theorem exact (x y z : ℕ) (h1 : x + y = 37) (h2 : 3 * x + z = 42) : x + y = 37 := by sorry
  theorem exact2 (x y : ℕ) (h : 0 + x = 0 + y + 2) : x = y + 2 := by sorry
  theorem apply (x y : ℕ) (h1 : x = 37) (h2 : x = 37 → y = 42) : y = 42 := by sorry
  theorem succ_inj (x : ℕ) (h : x + 1 = 4) : x = 3 := by sorry
  theorem succ_inj2 (x : ℕ) (h : x + 1 = 4) : x = 3 := by sorry
  theorem intro (x : ℕ) : x = 37 → x = 37 := by sorry
  theorem intro2  (x y : ℕ) : x + 1 = y + 1 → x = y := by sorry
  theorem NE (x y : ℕ) (h1 : x = y) (h2 : x ≠ y) : False := by sorry
  theorem zero_ne_one : (0 : ℕ) ≠ 1 := by sorry
  theorem one_ne_zero : (1 : ℕ) ≠ 0 := by sorry
  theorem two_add_two_ne_five : succ (succ 0) + succ (succ 0) ≠ succ (succ (succ (succ (succ 0)))) := by sorry
end Implication

section LessOrEqual
open Nat
  theorem le_refl (x : ℕ) : x ≤ x := by sorry
  theorem zero_le (x : ℕ) : 0 ≤ x := by sorry
  theorem le_succ_self (x : ℕ) : x ≤ succ x := by sorry
  theorem le_trans (x y z : ℕ) (hxy : x ≤ y) (hyz : y ≤ z) : x ≤ z := by sorry
  theorem le_zero (x : ℕ) (hx : x ≤ 0) : x = 0 := by sorry
  theorem le_antisymm (x y : ℕ) (hxy : x ≤ y) (hyx : y ≤ x) : x = y := by sorry
  theorem or_symm (x y : ℕ) (h : x = 37 ∨ y = 42) : y = 42 ∨ x = 37 := by sorry
  theorem le_total (x y : ℕ) : x ≤ y ∨ y ≤ x := by sorry
  theorem succ_le_succ (x y : ℕ) (hx : succ x ≤ succ y) : x ≤ y := by sorry
  theorem le_one (x : ℕ) (hx : x ≤ 1) : x = 0 ∨ x = 1 := by sorry
  theorem le_two (x : ℕ) (hx : x ≤ 2) : x = 0 ∨ x = 1 ∨ x = 2 := by sorry
  theorem one_add_le_self (x : ℕ) : x ≤ 1 + x := by sorry
  theorem refl (x : ℕ) : x ≤ x := by sorry
  theorem le_implies_le_plus_one (a b : ℕ) : a ≤ b → a ≤ (succ b) := by sorry
end LessOrEqual

section Multiplication
open Nat
  theorem mul_one (m : ℕ) : m * 1 = m := by sorry
  theorem zero_mul (m : ℕ) : 0 * m = 0 := by sorry
  theorem succ_mul (a b : ℕ) : succ a * b = a * b + b := by sorry
  theorem mul_comm (a b : ℕ) : a * b = b * a := by sorry
  theorem one_mul (m : ℕ): 1 * m = m := by sorry
  theorem two_mul (m : ℕ): 2 * m = m + m := by sorry
  theorem mul_add (a b c : ℕ) : a * (b + c) = a * b + a * c := by sorry
  theorem add_mul (a b c : ℕ) : (a + b) * c = a * c + b * c := by sorry
  theorem mul_assoc (a b c : ℕ) : (a * b) * c = a * (b * c)  := by sorry
end Multiplication

section OldAdvMultiplication
  theorem product_not_zero_of_not_zero (a b : ℕ) : a ≠ 0 → b ≠ 0 → a * b ≠ 0 := by sorry
  theorem MyNat.eq_zero_or_eq_zero_of_mul_eq_zero (a b : ℕ) (h : a * b = 0) :  a = 0 ∨ b = 0 := by sorry
  theorem product_zero_iff_zero {a b : ℕ} : a * b = 0 ↔ a = 0 ∨ b = 0 := by sorry
  theorem MyNat.mul_left_cancel (a b c : ℕ) (ha : a ≠ 0) : a * b = a * c → b = c := by sorry
  theorem MyNat.mul_left_comm (a b c : ℕ) : a * (b * c) = b * (a * c) := by sorry
end OldAdvMultiplication

section OldAdvProposition
  theorem P_and_Q_implies_PANDQ (P Q : Prop) (p : P) (q : Q) : P ∧ Q := by sorry
  theorem and_symm (P Q : Prop) : P ∧ Q → Q ∧ P :=  by sorry
  theorem and_trans (P Q R : Prop) : P ∧ Q → Q ∧ R → P ∧ R := by sorry
  theorem iff_trans (P Q R : Prop) : (P ↔ Q) → (Q ↔ R) → (P ↔ R) := by sorry
  theorem Q_implies_PORQ (P Q : Prop) : Q → (P ∨ Q) := by sorry
  theorem or_trans  (P Q : Prop) : P ∨ Q → Q ∨ P := by sorry
  theorem and_or_distrib_left (P Q R : Prop) : P ∧ (Q ∨ R) ↔ (P ∧ Q) ∨ (P ∧ R) := by sorry
  theorem contra (P Q : Prop) : (P ∧ ¬ P) → Q := by sorry
  theorem implies_trad (P Q : Prop) : (¬ Q → ¬ P) → (P → Q) := by sorry
end OldAdvProposition

section OldFunction
  example (P Q : Type) (p : P) (h : P → Q) : Q := by sorry
  example : ℕ → ℕ := by sorry
  example (P Q R S T U: Type) (p : P) (h : P → Q) (i : Q → R) (j : Q → T) (k : S → T) (l : T → U) : U := by sorry
  example (P Q R S T U: Type)
        (p : P)
        (h : P → Q)
        (i : Q → R)
        (j : Q → T)
        (k : S → T)
        (l : T → U) : U := by sorry
  example (P Q : Type) : P → (Q → P) := by sorry
  example (P Q R : Type) : (P → (Q → R)) → ((P → Q) → (P → R)) := by sorry
  example (P Q F : Type) : (P → Q) → ((Q → F) → (P → F)) := by sorry
  example (P Q : Type) : (P → Q) → ((Q → Empty) → (P → Empty)) := by sorry
  example (A B C D E F G H I J K L : Type)
    (f1 : A → B) (f2 : B → E) (f3 : E → D) (f4 : D → A) (f5 : E → F)
    (f6 : F → C) (f7 : B → C) (f8 : F → G) (f9 : G → J) (f10 : I → J)
    (f11 : J → I) (f12 : I → H) (f13 : E → H) (f14 : H → K) (f15 : I → L) : A → L := by sorry
end OldFunction

section OldProposition
  theorem level01 (P Q : Prop) (p : P) (h : P → Q) : Q := by sorry
  theorem level02 {P : Prop} : P → P := by sorry
  theorem level03 (P Q R S T U: Prop) (p : P) (h : P → Q) (i : Q → R)
    (j : Q → T) (k : S → T) (l : T → U) : U := by sorry
  theorem level04 (P Q R S T U: Prop) (p : P) (h : P → Q) (i : Q → R)
    (j : Q → T) (k : S → T) (l : T → U) : U := by sorry
  theorem level05 (P Q : Prop) : P → (Q → P) := by sorry
  theorem level06 (P Q R : Prop) : (P → (Q → R)) → ((P → Q) → (P → R)) := by sorry
  theorem level07 (P Q R : Prop) : (P → Q) → ((Q → R) → (P → R)) := by sorry
  theorem level08 (P Q : Prop) : (P → Q) → (¬ Q → ¬ P) := by sorry
  theorem level09     (A B C D E F G H I J K L : Prop)
    (f1 : A → B) (f2 : B → E) (f3 : E → D) (f4 : D → A) (f5 : E → F)
    (f6 : F → C) (f7 : B → C) (f8 : F → G) (f9 : G → J) (f10 : I → J)
    (f11 : J → I) (f12 : I → H) (f13 : E → H) (f14 : H → K) (f15 : I → L) : A → L := by sorry
end OldProposition

section Power
open Nat
  theorem zero_pow_zero : (0 : ℕ) ^ 0 = 1 := by sorry
  theorem zero_pow_any (m : ℕ) : (0 : ℕ) ^ (succ m) = 0 := by sorry
  theorem any_pow_one (a : ℕ) : a ^ 1 = a  := by sorry
  theorem one_pow_any (m : ℕ) : (1 : ℕ) ^ m = 1 := by sorry
  theorem pow_two (a : ℕ) : a ^ 2 = a * a := by sorry
  theorem pow_add (a m n : ℕ) : a ^ (m + n) = a ^ m * a ^ n := by sorry
  theorem mul_pow (a b n : ℕ) : (a * b) ^ n = a ^ n * b ^ n := by sorry
  theorem pow_pow (a m n : ℕ) : (a ^ m) ^ n = a ^ (m * n) := by sorry
  theorem add_sq (a b : ℕ) : (a + b) ^ 2 = a ^ 2 + b ^ 2 + 2 * a * b := by sorry
  theorem level10 (a b c n : ℕ) : (a + 1) ^ (n + 3) + (b + 1) ^ (n + 3) ≠ (c + 1) ^ (n + 3) := by sorry
end Power

section Tutorial
open Nat
  theorem level01rfl (x q : ℕ) : 37 * x + q = 37 * x + q := by sorry
  theorem level02rw (x y : ℕ) (h : y = x + 7) : 2 * y = 2 * (x + 7) := by sorry
  theorem level03_two_eq_succ_succ_zero : 2 = succ (succ 0) := by sorry
  theorem level04_rw_backwards : 2 = succ (succ 0) := by sorry
  theorem level05_add_zero (a b c : ℕ) : a + (b + 0) + (c + 0) = a + b + c := by sorry
  theorem level06_add_zero2 (a b c : ℕ) : a + (b + 0) + (c + 0) = a + b + c := by sorry
  theorem succ_eq_add_one n : succ n = n + 1 := by sorry
  theorem level08_two_add_two : (2 : ℕ) + 2 = 4 := by sorry
end Tutorial

section WIPAlgorithm
  theorem l11_accrfl (a b c d e f g h : ℕ) :
    (d + f) + (h + (a + c)) + (g + e + b) = a + b + c + d + e + f + g + h := by sorry
end WIPAlgorithm

section WIPFuncProg
  theorem decide01 : (20 : ℕ) + 20 = 40 := by sorry
  theorem decode02 : (29 : ℕ) + 35 = 64 := by sorry
end WIPFuncProg

end BlasterBenchmarks.NNG4
