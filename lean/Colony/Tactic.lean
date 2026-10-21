import Lean
import Std.Tactic
import Colony.Procedures.ListState

open Lean Elab Tactic Meta

namespace Colony

/-- A fixed, ordered collection of ordinary natural-order rules. No rule is
selected by the name or definition of a benchmark. -/
private def orderRules : Array Name :=
  #[``Nat.mul_le_mul, ``Nat.add_le_add, ``Nat.le_trans]

/-- At most four rule applications per branch, with assumption leaves.
All rules have two premises, so an accepted tree has at most 31 nodes.
Each failed candidate restores its full state before the next is tried. -/
private def boundedOrderSearch : Nat → TacticM Unit
  | 0 => do evalTactic (← `(tactic| assumption))
  | fuel + 1 => do
    let start ← saveState
    try
      evalTactic (← `(tactic| assumption))
      return
    catch _ => start.restore
    for rule in orderRules do
      try
        let subgoals ← (← getMainGoal).apply (← mkConstWithFreshMVarLevels rule)
        for subgoal in subgoals do
          unless (← subgoal.isAssigned) do
            setGoals [subgoal]
            boundedOrderSearch fuel
        setGoals []
        return
      catch _ => start.restore
    throwError "colony: bounded order search found no chain"

private def arithmeticPortfolio : TacticM Unit := do
  let start ← saveState
  try
    boundedOrderSearch 4
    unless (← getGoals).isEmpty do
      throwError "colony: bounded order search left goals"
    return
  catch _ => start.restore
  evalTactic (← `(tactic| first
    | (solve | omega)
    | (solve | simp_all <;> omega)
    | (solve | ac_rfl)
    | (solve | decide)))

private def orderedProductPortfolio : TacticM Unit := do
  -- Nat multiplication is monotone in its left argument for every right factor.
  -- `assumption` must find the premise; this step cannot manufacture a bound.
  evalTactic (← `(tactic| solve | apply Nat.mul_le_mul_right; assumption))

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

/-- Split one product-valued local and close every resulting branch. -/
private def productPortfolio (subject : Ident) : TacticM Unit := do
  evalTactic (← `(tactic| cases $subject:ident))
  let branches ← getGoals
  for branch in branches do
    setGoals [branch]
    evalTactic (← `(tactic| solve | simp_all <;> omega))
  setGoals []

/-- Try at most eight same-typed pairs of local terms, splitting each candidate
with `by_cases`. Search depth is capped at two. Each candidate has a complete
state snapshot, so an unsuccessful split leaves no branch or local hypothesis. -/
private def equalitySplitSearch : Nat → TacticM Unit
  | 0 => do evalTactic (← `(tactic| solve | simp_all <;> omega))
  | depth + 1 => do
    let locals ← withMainContext do
      let mut found : Array LocalDecl := #[]
      for decl in (← getLCtx) do
        unless decl.isImplementationDetail do
          unless (← isProp decl.type) do
            found := found.push decl
      return found
    let mut attempts := 0
    for i in [:locals.size] do
      for j in [i+1:locals.size] do
        if attempts < 8 && (← isDefEq locals[i]!.type locals[j]!.type) then
          attempts := attempts + 1
          let snapshot ← saveState
          try
            let left := mkIdent locals[i]!.userName
            let right := mkIdent locals[j]!.userName
            evalTactic (← `(tactic| by_cases h : $left:ident = $right:ident))
            let branches ← getGoals
            for branch in branches do
              setGoals [branch]
              equalitySplitSearch depth
            setGoals []
            return
          catch _ => snapshot.restore
    throwError "colony: bounded equality split found no proof"


private def listProcessInduction (subject : Ident) (generalized : Array Ident) : TacticM Unit := do
  evalTactic (← `(tactic| induction $subject:ident generalizing $[$generalized:ident]*))
  let branches ← getGoals
  for branch in branches do
    setGoals [branch]
    try
      evalTactic (← `(tactic| solve |
        simp_all [Colony.Procedure.process, Colony.Procedure.step] <;> omega))
    catch _ =>
      let branchState ← saveState
      try
        equalitySplitSearch 2
      catch _ =>
        branchState.restore
        let command ← withMainContext do
          let mut found : Option Ident := none
          for decl in (← getLCtx) do
            unless decl.isImplementationDetail do
              if (← whnf decl.type).isConstOf ``Colony.Procedure.ListCommand then
                found := some (mkIdent decl.userName)
          return found
        match command with
        | none => throwError "colony: induction branch has no eligible equality or command"
        | some command =>
          evalTactic (← `(tactic| cases $command:ident))
          for splitBranch in (← getGoals) do
            setGoals [splitBranch]
            evalTactic (← `(tactic| solve |
              simp_all [Colony.Procedure.process, Colony.Procedure.step] <;> omega))
  setGoals []

private def boundedStructuralInduction (subject : Ident) (generalized : Array Ident) : TacticM Unit := do
  evalTactic (← `(tactic| induction $subject:ident generalizing $[$generalized:ident]*))
  for branch in (← getGoals) do
    setGoals [branch]
    let snapshot ← saveState
    try
      evalTactic (← `(tactic| solve | simp_all <;> omega))
    catch _ =>
      snapshot.restore
      equalitySplitSearch 2
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
  try
    orderedProductPortfolio
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
  -- Use local-context order and attempt at most one product candidate at a time.
  -- A candidate is committed only if its complete split tree closes.
  let productSolved ← withMainContext do
    let context ← getLCtx
    for decl in context do
      unless decl.isImplementationDetail do
        if (← whnf decl.type).isAppOf ``Prod then
          let candidateState ← saveState
          try
            productPortfolio (mkIdent decl.userName)
            return true
          catch _ => candidateState.restore
    return false
  if productSolved then
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
            boundedStructuralInduction subject generalized
            return
          catch _ => initial.restore
    throwError "colony: the initial proof portfolio could not close this goal"

end Colony
