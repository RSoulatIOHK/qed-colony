import Colony.Tactic

namespace Colony.Examples.OrderedProduct

/-- A bounded product of a finite list of natural number factors. -/
def orderedProduct (factors : List Nat) : Nat := factors.foldr (· * ·) 1

/-- Compose three independently established product monotonicity steps. -/
theorem orderedProduct_chain
    (a b c d : List Nat)
    (hab : orderedProduct a ≤ orderedProduct b)
    (hbc : orderedProduct b ≤ orderedProduct c)
    (hcd : orderedProduct c ≤ orderedProduct d) :
    orderedProduct a ≤ orderedProduct d := by colony

/-- Product monotonicity must be applied before the three supplied order links
can establish the left factor of the requested inequality. -/
theorem orderedProduct_mul_chain
    (a b c d : List Nat) (x y : Nat)
    (hab : orderedProduct a ≤ orderedProduct b)
    (hbc : orderedProduct b ≤ orderedProduct c)
    (hcd : orderedProduct c ≤ orderedProduct d)
    (hxy : x ≤ y) :
    orderedProduct a * x ≤ orderedProduct d * y := by colony

/-- The existing arithmetic fallback cannot establish this nonlinear goal. -/
example (a b c d : List Nat) (x y : Nat)
    (hab : orderedProduct a ≤ orderedProduct b)
    (hbc : orderedProduct b ≤ orderedProduct c)
    (hcd : orderedProduct c ≤ orderedProduct d)
    (hxy : x ≤ y) : True := by
  fail_if_success
    (have : orderedProduct a * x ≤ orderedProduct d * y := by omega)
  fail_if_success
    (have : orderedProduct a * x ≤ orderedProduct d * y := by simp_all <;> omega)
  fail_if_success
    (have : orderedProduct a * x ≤ orderedProduct d * y := by decide)
  trivial

/-- The intended invalid/reversed direction is rejected by the tactic. -/
example (a b : List Nat) (h : orderedProduct b ≤ orderedProduct a) :
    True := by
  fail_if_success
    (have : orderedProduct a ≤ orderedProduct b := by colony)
  trivial

/-- A reversed factor inequality cannot justify the product conclusion. -/
example (a b : List Nat) (x y : Nat)
    (hab : orderedProduct a ≤ orderedProduct b) (hyx : y ≤ x) : True := by
  fail_if_success
    (have : orderedProduct a * x ≤ orderedProduct b * y := by colony)
  trivial

/-- The reversed factor hypothesis admits a concrete counterexample. -/
example : ¬ (orderedProduct [] * 2 ≤ orderedProduct [] * 1) := by decide

/-- The assumptions have a concrete nonzero model with strict increases. -/
example : orderedProduct [2] ≤ orderedProduct [3] ∧
    orderedProduct [3] ≤ orderedProduct [4] ∧
    orderedProduct [4] ≤ orderedProduct [5] ∧ (2 : Nat) ≤ 3 := by decide

/-- Four nested rule applications compose on opaque factors. -/
theorem orderedProduct_nested
    (a b : List Nat) (x y u v z w r s : Nat)
    (hab : orderedProduct a ≤ orderedProduct b)
    (hxy : x ≤ y) (huv : u ≤ v) (hzw : z ≤ w) (hrs : r ≤ s) :
    (orderedProduct a * x + u) * z + r ≤ (orderedProduct b * y + v) * w + s := by colony

/-- An irrelevant first order fact does not prevent this valid chain. -/
theorem orderedProduct_distractor
    (a b c d : List Nat) (x y : Nat)
    (hnoise : orderedProduct a ≤ orderedProduct a)
    (hab : orderedProduct a ≤ orderedProduct b)
    (hbc : orderedProduct b ≤ orderedProduct c)
    (hcd : orderedProduct c ≤ orderedProduct d) (hxy : x ≤ y) :
    orderedProduct a * x ≤ orderedProduct d * y := by colony

#print axioms orderedProduct_chain
#print axioms orderedProduct_mul_chain
#print axioms orderedProduct_nested
#print axioms orderedProduct_distractor

end Colony.Examples.OrderedProduct
