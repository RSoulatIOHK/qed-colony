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

/-- Explicitly split the nested constructors, then use `colony`'s arithmetic
portfolio on each resulting branch (one constructor split per invocation). -/
theorem step_advances (response : Response) (retries : Nat) :
    step retries response > retries := by
  cases response with
  | none => simp only [step]; colony
  | some result =>
      simp only [step]
      cases result with
      | error reason =>
          cases reason <;> simp only [step]; all_goals colony
      | ok value => simp only [step]; colony

example (response : Response) (retries : Nat) : True := by
  fail_if_success
    (have : step retries response > retries + 3 := by
      colony)
  trivial

end Colony.Examples.NestedResultTransition
