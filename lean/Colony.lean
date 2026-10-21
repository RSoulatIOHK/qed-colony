import Colony.Tactic
import Colony.Seeds
import Colony.Examples.BooleanBranching
import Colony.Examples.OptionBranching
import Colony.Examples.ResultFlow
import Colony.Examples.ListStateInvariant
import Colony.Examples.AccumulatorLength

namespace Colony

/-- A local adapter connecting the accumulator implementation to list reversal. -/
theorem reverseAcc_bridge (xs acc : List Nat) :
    Seed.reverseAcc xs acc = xs.reverse ++ acc := by
  induction xs generalizing acc with
  | nil => simp [Seed.reverseAcc]
  | cons x xs ih =>
      simp [Seed.reverseAcc, ih, List.reverse_cons, List.append_assoc]

end Colony
