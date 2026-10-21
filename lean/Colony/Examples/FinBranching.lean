import Colony.Tactic

namespace Colony.Examples.FinBranching

/-- A value that distinguishes zero from every successor index. -/
@[simp] def marker {n : Nat} : Fin (Nat.succ n) → Nat :=
  Fin.cases 0 (fun _ => 1)

/-- The bound follows from the zero/successor structure of the finite index. -/
theorem marker_bounded {n : Nat} (i : Fin (Nat.succ n)) :
    marker i ≤ i.val + 1 := by
  colony

example (n : Nat) : marker (⟨0, by omega⟩ : Fin (Nat.succ n)) = 0 := by
  simp [marker]

/-- Colony must reject the adjacent false claim at a successor index. -/
example {n : Nat} (i : Fin (Nat.succ n)) : True := by
  fail_if_success
    (have : marker i < 1 := by
      colony)
  trivial

#print axioms marker_bounded

end Colony.Examples.FinBranching
