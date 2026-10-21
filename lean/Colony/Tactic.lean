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

private def listProcessInduction (subject : Ident) (generalized : Array Ident) : TacticM Unit := do
  evalTactic (← `(tactic| induction $subject:ident generalizing $[$generalized:ident]*))
  let branches ← getGoals
  for branch in branches do
    setGoals [branch]
    try
      evalTactic (← `(tactic| solve |
        simp_all [Colony.Procedure.process, Colony.Procedure.step] <;> omega))
    catch _ =>
      let command ← withMainContext do
        let context ← getLCtx
        let mut found : Option Ident := none
        for decl in context do
          unless decl.isImplementationDetail do
            if (← whnf decl.type).isConstOf ``Colony.Procedure.ListCommand then
              found := some (mkIdent decl.userName)
        return found
      match command with
      | none => throwError "colony: induction branch lacks a command constructor"
      | some command =>
        evalTactic (← `(tactic| cases $command:ident))
        let splitBranches ← getGoals
        for splitBranch in splitBranches do
          setGoals [splitBranch]
          evalTactic (← `(tactic| solve |
            simp_all [Colony.Procedure.process, Colony.Procedure.step] <;> omega))
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
  let listInductionSolved ← withMainContext do
    let context ← getLCtx
    let mut candidates : Array LocalDecl := #[]
    for decl in context do
      unless decl.isImplementationDetail do
        let type ← whnf decl.type
        if type.isAppOf ``List then
          let args := type.getAppArgs
          if args.size == 1 && args[0]!.isConstOf ``Colony.Procedure.ListCommand then
            candidates := candidates.push decl
    if candidates.size != 1 then
      return false
    let candidateState ← saveState
    let mut generalized : Array Ident := #[]
    for decl in context do
      unless decl.isImplementationDetail || decl.userName == candidates[0]!.userName do
        unless (← isProp decl.type) do
          generalized := generalized.push (mkIdent decl.userName)
    try
      listProcessInduction (mkIdent candidates[0]!.userName) generalized
      return true
    catch _ =>
      candidateState.restore
      return false
  if listInductionSolved then
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
