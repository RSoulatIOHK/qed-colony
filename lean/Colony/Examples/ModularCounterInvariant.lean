import Colony.Tactic

namespace Colony.Examples.ModularCounterInvariant

structure State where
  updates : Nat
  deriving Repr, DecidableEq

/-- Advance a bounded program counter and record exactly when it wraps. -/
def step {n : Nat} (pc : Fin (n + 1)) (state : State) : Fin (n + 1) × State :=
  let wrapped := pc.val == n
  (⟨(pc.val + 1) % (n + 1), Nat.mod_lt _ (Nat.succ_pos _)⟩,
    ⟨state.updates + if wrapped then 1 else 0⟩)

/-- The state update records the wrap detected by the successor counter. -/
theorem step_records_wrap {n : Nat} (pc : Fin (n + 1)) (state : State) :
    (step pc state).2.updates = state.updates +
      if (step pc state).1.val = 0 then 1 else 0 := by
  fail_if_success colony
  simp only [step, Bool, Fin.val_mk]
  by_cases h : pc.val = n
  · simp [h, Nat.mod_self]
  · have hlt : pc.val + 1 < n + 1 := by omega
    have hmod : (pc.val + 1) % (n + 1) = pc.val + 1 := Nat.mod_eq_of_lt hlt
    simp [step, h, hmod]

#print axioms step_records_wrap

/-- Frozen nearby false control: every transition does not wrap. -/
example : ¬ (step (n := 1) ⟨0, by omega⟩ ⟨0⟩).2.updates = 1 := by
  fail_if_success
    (have : (step (n := 1) ⟨0, by omega⟩ ⟨0⟩).2.updates = 1 := by
      colony)
  decide

end Colony.Examples.ModularCounterInvariant
