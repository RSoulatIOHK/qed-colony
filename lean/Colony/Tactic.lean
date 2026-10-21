import Lean
import Std.Tactic

open Lean Elab Tactic Meta

namespace Colony

private def arithmeticPortfolio : TacticM Unit := do
  evalTactic (← `(tactic| first
    | (solve | omega)
    | (solve | simp_all <;> omega)
    | (solve | decide)))

private def booleanPortfolio (subject : Ident) : TacticM Unit := do
  evalTactic (← `(tactic| cases $subject:ident))
  let branches ← getGoals
  for branch in branches do
    setGoals [branch]
    arithmeticPortfolio
  setGoals []

/--
The initial deterministic proof portfolio: simplification, Presburger arithmetic,
closed decision procedures, and one structural induction on a list or natural.
Every successful branch constructs an ordinary Lean proof term. This is a seed
implementation, not the intended final architecture.
-/
elab "colony" : tactic => do
  evalTactic (← `(tactic| intros))
  let initial ← saveState
  try
    arithmeticPortfolio
    return
  catch _ => initial.restore
  let booleanSolved ← withMainContext do
    let context ← getLCtx
    for decl in context do
      unless decl.isImplementationDetail do
        if (← whnf decl.type).isConstOf ``Bool then
          let candidateState ← saveState
          try
            booleanPortfolio (mkIdent decl.userName)
            return true
          catch _ => candidateState.restore
    return false
  if booleanSolved then
    return
  try
    let bridge := mkIdent (.str (.mkSimple "Colony") "reverseAcc_bridge")
    evalTactic (← `(tactic| solve |
      simp only [$bridge:ident, List.append_nil, List.reverse_reverse]))
    return
  catch _ => initial.restore
  withMainContext do
    let context ← getLCtx
    for decl in context do
      unless decl.isImplementationDetail do
        let type ← whnf decl.type
        if type.isAppOf ``List || type.isConstOf ``Nat then
          let subject := mkIdent decl.userName
          let mut generalized : Array Ident := #[]
          for other in context do
            unless other.isImplementationDetail || other.fvarId == decl.fvarId do
              generalized := generalized.push (mkIdent other.userName)
          try
            if generalized.isEmpty then
              evalTactic (← `(tactic| solve |
                induction $subject:ident <;>
                  (simp_all [process, step] <;> omega)))
            else
              evalTactic (← `(tactic| solve |
                induction $subject:ident generalizing $[$generalized:ident]* <;>
                  (simp_all [process, step] <;> omega)))
            return
          catch _ => initial.restore
    throwError "colony: the initial proof portfolio could not close this goal"

end Colony
