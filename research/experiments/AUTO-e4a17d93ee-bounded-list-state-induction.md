# AUTO-e4a17d93ee: bounded induction for the list-state invariant

## Scope and source

Base revision: `e1892b16c65d85d960b079970c5547cc050bb978` (working tree changes are uncommitted).
The project toolchain is Lean `v4.35.0` (`lean/lean-toolchain`). The theorem statement, `process` definition, assumptions, and false sequence-property control are unchanged. The theorem body now invokes `by colony`.

The new candidate runs only when exactly one local declaration has type `List ListCommand`. It structurally inducts on that declaration and generalizes the other non-propositional local declarations. Each branch uses the fixed solver `simp_all [Colony.Procedure.process, Colony.Procedure.step] <;> omega`; if the initial branch attempt fails, it splits a local `ListCommand` and applies that same solver. The full candidate is wrapped in saved-state restoration, so any failure returns to the pre-candidate tactic state.

## Failed attempts and diagnostics

An initial implementation tried to filter the local context with `LocalContext.filterM` and failed to compile. Lean reported:

```text
Invalid field `filterM`: The environment does not contain `Lean.LocalContext.filterM`
```

It was replaced with an explicit context loop.

The first induction helper hard-coded the generalized binder name `state`. A build failed with:

```text
error: Colony/Examples/ListStateInvariant.lean:27:2: Unknown identifier `state✝`
```

The generated binder name was inaccessible under that syntax. The helper now obtains all eligible generalized identifiers from the local context.

The next branch shape attempted only `simp_all [process, step] <;> omega`. The observed induction goals were:

```text
case nil
state : ListState
h : state.balance = state.recorded
⊢ (process [] state).balance = (process [] state).recorded

case cons
head✝ : ListCommand
tail✝ : List ListCommand
tail_ih✝ : ∀ (state : ListState), state.balance = state.recorded →
  (process tail✝ state).balance = (process tail✝ state).recorded
state : ListState
h : state.balance = state.recorded
⊢ (process (head✝ :: tail✝) state).balance = (process (head✝ :: tail✝) state).recorded
```

The cons case needs command constructor splitting before simplification. Since Lean generates inaccessible names such as `head✝`, the solver now discovers the local command declaration rather than referring to a source-level name. Before that adjustment, the externally visible tactic diagnostic was:

```text
error: Colony/Examples/ListStateInvariant.lean:27:2: colony: the initial proof portfolio could not close this goal
```

## Commands and outputs

Commands were run from the `lean/` project directory unless stated otherwise.

```sh
lake build Colony
```

After the induction candidate was complete:

```text
✔ [3/8] Built Colony.Tactic
✔ [4/8] Built Colony.Examples.BooleanBranching
✔ [5/8] Built Colony.Examples.ListStateInvariant
✔ [6/8] Built Colony.Seeds
✔ [7/8] Built Colony
Build completed successfully (8 jobs).
```

```sh
lake build
```

```text
✔ [6/10] Replayed Colony.Examples.ListStateInvariant
✔ [9/10] Built SeedProofs
Build completed successfully (10 jobs).
```

The full build also prints expected axiom reports for unrelated `SeedProofs` examples. The target theorem was checked separately:

```sh
lake env lean --stdin <<'EOF'
import Colony.Examples.ListStateInvariant
#print axioms Colony.Examples.process_preserves_list_state_invariant
EOF
```

Output:

```text
'Colony.Examples.process_preserves_list_state_invariant' depends on axioms: [propext]
```

`propext` is Lean's standard propositional extensionality axiom; no `sorry`, `admit`, arbitrary axiom, native evaluation axiom, or disabled kernel check was introduced. The false sequence-property remains inside `fail_if_success` and the project build succeeds with that guard in place.

From the repository root, `git diff --check` completed with exit code 0 and no output.

## Assurance and limits

The build provides ordinary Lean elaborator kernel acceptance for the theorem and examples. The theorem's axiom report contains only `[propext]`. No exported replay, independent-kernel acceptance, tamper-proof evaluator result, or correspondence to Cardano execution is claimed. The tactic is deterministic and local, and this candidate is deliberately narrow: it requires exactly one visible `List ListCommand` local declaration and generalizes other non-propositional locals. The existing generic induction portfolio remains separate.
