import Colony.Tactic

namespace Colony.Examples.RecursiveKeyedInvariant

/-- Replace every occurrence of a key in a recursive list state. -/
@[simp] def replaceKey (key value : Nat) : List Nat → List Nat
  | [] => []
  | head :: tail =>
      (if head = key then value else head) :: replaceKey key value tail

@[simp] def sumExcept (key : Nat) : List Nat → Nat
  | [] => 0
  | head :: tail => (if head = key then 0 else head) + sumExcept key tail

theorem replaceKey_preserves_other_sum (state : List Nat) (key value : Nat) :
    sumExcept key (replaceKey key value state) = sumExcept key state := by
  colony

example (state : List Nat) (key value : Nat) : True := by
  fail_if_success
    (have false_invariant :
      sumExcept key (replaceKey key value state) = sumExcept key state + 1 := by
      colony)
  trivial

end Colony.Examples.RecursiveKeyedInvariant
