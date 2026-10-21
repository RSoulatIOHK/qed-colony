import Colony.Tactic

namespace Colony.Examples

/- Copy each input element into both threaded accumulators. -/
@[simp]
def copyIntoBoth (xs left right : List Nat) : List Nat × List Nat :=
  match xs with
  | [] => (left, right)
  | x :: rest => copyIntoBoth rest (x :: left) (x :: right)

/-- Each output accumulator gains exactly the length of the input. -/
theorem copyIntoBoth_lengths (xs left right : List Nat) :
    (copyIntoBoth xs left right).1.length = xs.length + left.length ∧
    (copyIntoBoth xs left right).2.length = xs.length + right.length := by
  colony

example (xs left right : List Nat) : True := by
  fail_if_success
    (have : (copyIntoBoth xs left right).1.length = xs.length + left.length + 1 := by
      colony)
  trivial

end Colony.Examples
