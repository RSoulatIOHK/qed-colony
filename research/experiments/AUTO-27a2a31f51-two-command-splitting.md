# AUTO-27a2a31f51: bounded constructor splitting for two commands

## Scope and candidate

Base revision: `e1892b16c65d85d960b079970c5547cc050bb978`. The target was a
positive theorem over arbitrary `first second : ListCommand`, with the unchanged
`process` semantics and the existing initial-state equality assumption:

```lean
(process [first, second] state).balance =
  (process [first, second] state).recorded
```

The single candidate extended the command case-splitting fallback to select the
first two local `ListCommand` values in context order, split each exactly once,
and solve all resulting branches with the existing deterministic branch script
`simp_all [Colony.Procedure.step] <;> omega`. Thus the bound was two command
values (nine constructor branches), with no recursive splitting or alternate
scripts. The candidate replaced the existing one-command split.

## Result and diagnostics

Command: `lake build Colony` from `lean/`; exit 1. `Colony.Tactic` compiled,
but `Colony.Examples.ListStateInvariant` failed. Lean reported:

```text
error: Colony/Examples/ListStateInvariant.lean:13:2: colony: the initial proof portfolio could not close this goal
error: Colony/Examples/ListStateInvariant.lean:21:2: colony: the initial proof portfolio could not close this goal
```

The first diagnostic is the existing one-command invariant, which the candidate
regressed because it requires only one local command. The second is the two-
command target; it too remained open. The candidate restored tactic state after
branch failure, so the final diagnostic was the outer portfolio error. No
successful target or nearby-invalid rejection was established. Following the
fixed-candidate stop condition, no alternate branch order or solver was tried.

The experiment was reverted; tracked Lean files are unchanged. The tested
candidate was transient and is not the current source. The build also compiled
the existing Boolean examples and `Colony.Seeds` before failing at the list-state
example; no claim is made that the full existing examples or R003 frontier build
under that candidate. No post-revert build was run.

## Assurance

No proof assurance is claimed for the target: it was not kernel accepted. The
failed build is evidence only of ordinary tactic failure. No `sorry`, `admit`,
or axiom was introduced. The base source revision and theorem statements were
left unchanged.
