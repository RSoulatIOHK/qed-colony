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

/-- The intended invalid/reversed direction is rejected by the tactic. -/
example (a b : List Nat) (h : orderedProduct b ≤ orderedProduct a) :
    True := by
  fail_if_success
    (have : orderedProduct a ≤ orderedProduct b := by colony)
  trivial

end Colony.Examples.OrderedProduct
