import Colony.Tactic

namespace Colony.Examples

/-- Copy the input into an accumulator while preserving every element. -/
def copyInto (xs acc : List Nat) : List Nat :=
  match xs with
  | [] => acc
  | x :: rest => copyInto rest (x :: acc)

/-- The procedure's output length is unchanged from the two input lengths. -/
theorem copyInto_length (xs acc : List Nat) :
    (copyInto xs acc).length = xs.length + acc.length := by
  fail_if_success colony
  induction xs generalizing acc with
  | nil => simp [copyInto]
  | cons x rest ih =>
      simpa [copyInto, ih, Nat.add_assoc, Nat.add_comm, Nat.add_left_comm]

example (xs acc : List Nat) : True := by
  fail_if_success
    (have : (copyInto xs acc).length = xs.length + acc.length + 1 := by
      colony)
  trivial

end Colony.Examples
