import Colony.Tactic

namespace Colony.Examples.RecursiveKeyedInvariant

/-- Replace every occurrence of a key in a recursive list state. -/
@[simp] def replaceKey (key value : Nat) : List Nat → List Nat
  | [] => []
  | head :: tail =>
      (if head = key then value else head) :: replaceKey key value tail

@[simp] def sumExcept (key : Nat) : List Nat → Nat
  | [] => 0
  | head :: tail =>
      if head = key then sumExcept key tail
      else head + sumExcept key tail

@[simp] def sumState : List Nat → Nat
  | [] => 0
  | head :: tail => head + sumState tail

/-- Zeroing every matching entry leaves exactly the sum of the other entries. -/
theorem replaceKey_zero_sum (state : List Nat) (key : Nat) :
    sumState (replaceKey key 0 state) = sumExcept key state := by
  colony

example : sumState (replaceKey 2 0 [2, 3, 2]) = 3 ∧
    sumExcept 2 [2, 3, 2] = 3 ∧
    ¬ sumState (replaceKey 2 0 [2, 3, 2]) = sumExcept 2 [2, 3, 2] + 1 := by
  decide

example (state : List Nat) (key : Nat) : True := by
  fail_if_success
    (have false_invariant :
      sumState (replaceKey key 0 state) = sumExcept key state + 1 := by
      colony)
  trivial

end Colony.Examples.RecursiveKeyedInvariant
