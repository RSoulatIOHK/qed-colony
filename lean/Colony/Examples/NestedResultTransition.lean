import Colony.Tactic

namespace Colony.Examples.NestedResultTransition

inductive Failure where
  | rejected
  | unavailable
  deriving Repr, DecidableEq

/-- An absent response, or a response carrying either an error or a value. -/
abbrev Response := Option (Except Failure Nat)

/-- Every response advances the retry count; a successful value adds more. -/
def step (retries : Nat) (response : Response) : Nat :=
  match response with
  | none => retries + 3
  | some (.error _) => retries + 2
  | some (.ok value) => retries + value + 1

/-- A successful response advances by its value plus one. -/
private theorem step_ok (retries value : Nat) :
    step retries (some (.ok value)) > retries := by
  simp only [step]
  omega

/-- Either error constructor advances by two. -/
private theorem step_error (retries : Nat) (reason : Failure) :
    step retries (some (.error reason)) > retries := by
  simp only [step]
  omega

/-- The `colony` invocation splits the outer `Option` at depth one. The inner
`Except` obligations are proved by the two lemmas above. -/
theorem step_advances (response : Response) (retries : Nat) :
    step retries response > retries := by
  have hSome (result : Except Failure Nat) :
      step retries (some result) > retries := by
    cases result with
    | error reason => exact step_error retries reason
    | ok value => exact step_ok retries value
  simp only [step] at *
  fail_if_success (first
    | (solve | omega)
    | (solve | simp_all <;> omega)
    | (solve | decide))
  colony

/-- The stronger universal bound fails for the successful value zero. -/
example : ¬ (∀ response : Response, ∀ retries : Nat,
    step retries response > retries + 3) := by
  intro h
  have h0 := h (some (.ok 0)) 0
  simp [step] at h0

end Colony.Examples.NestedResultTransition
