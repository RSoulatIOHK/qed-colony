import Lean
import Std.Tactic
import Colony.Procedures.ListState

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

private def optionPortfolio (subject : Ident) : TacticM Unit := do
  evalTactic (← `(tactic| cases $subject:ident))
  let branches ← getGoals
  for branch in branches do
    setGoals [branch]
    arithmeticPortfolio
  setGoals []

/-- Split exactly one candidate; branch solvers do not call `colony` recursively.
The caller restores the complete candidate snapshot if any branch fails. -/
private def exceptPortfolio (subject : Ident) : TacticM Unit := do
  evalTactic (← `(tactic| cases $subject:ident))
  let branches ← getGoals
  for branch in branches do
    setGoals [branch]
    evalTactic (← `(tactic| first
      | (solve | simp_all <;> omega)
      | (solve | simp_all <;> decide)
      | (solve | omega)))
    unless (← getGoals).isEmpty do
      throwError "colony: an Except branch remains unsolved"
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
  let optionSolved ← withMainContext do
    let context ← getLCtx
    for decl in context do
      unless decl.isImplementationDetail do
        let type ← whnf decl.type
        if type.isAppOf ``Option then
          let candidateState ← saveState
          try
            optionPortfolio (mkIdent decl.userName)
            return true
          catch _ => candidateState.restore
    return false
  if optionSolved then
    return
  -- Context order is deterministic. Failed candidates do not accumulate splits:
  -- every attempt starts from its own saved, unsplit tactic state.
  let exceptSolved ← withMainContext do
    let context ← getLCtx
    for decl in context do
      unless decl.isImplementationDetail do
        let type ← whnf decl.type
        if type.isAppOf ``Except then
          let candidateState ← saveState
          try
            exceptPortfolio (mkIdent decl.userName)
            return true
          catch _ => candidateState.restore
    return false
  if exceptSolved then
    return
  let commandSolved ← withMainContext do
    let context ← getLCtx
    for decl in context do
      unless decl.isImplementationDetail do
        if (← whnf decl.type).isConstOf ``Colony.Procedure.ListCommand then
          let candidateState ← saveState
          try
            evalTactic (← `(tactic| cases $(mkIdent decl.userName):ident))
            let branches ← getGoals
            for branch in branches do
              setGoals [branch]
              evalTactic (← `(tactic| solve |
                simp_all [Colony.Procedure.step] <;> omega))
            setGoals []
            return true
          catch _ =>
            candidateState.restore
            return false
    return false
  if commandSolved then
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
              unless (← isProp other.type) do
                generalized := generalized.push (mkIdent other.userName)
          try
            if generalized.isEmpty then
              evalTactic (← `(tactic| solve |
                induction $subject:ident <;> (simp_all <;> omega)))
            else
              evalTactic (← `(tactic| solve |
                induction $subject:ident generalizing $[$generalized:ident]* <;>
                  (simp_all <;> omega)))
            return
          catch _ => initial.restore
    throwError "colony: the initial proof portfolio could not close this goal"

end Colony
