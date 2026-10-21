# AUTO-7e87e900e8: scope correction and direct-target verification

## Scope and acceptance before correction

Task base: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
Starting revision: `94205b2e1ab1f625e189ed8db09d6cb176634f8d`.

Remove the focused example's import from `lean/Colony.lean` so that the umbrella
module matches the task base exactly. Preserve the existing tactic, focused
positive theorem, assumptions, false-property witness, and procedure definitions.
Correct the previous report's inaccurate scope statement. Acceptance requires
direct builds of the tactic, focused example, and existing list-state example;
the focused Lean check must still report one successful bounded attempt, reject
the false properties and ambiguous candidate case, and print axiom dependencies.
Record the resulting source hashes and distinguish local kernel acceptance from
stronger assurance claims. No evaluator, policy, benchmark, challenge, CI, or
protected files are to change.

## Final source identity and scope

The checked source is the starting revision above plus this uncommitted scope
correction. No commit or publication was performed. Relative to the task base,
the only changed Lean modules are `Colony.Tactic` and the new
`Colony.Examples.BoundedListProcess`. The umbrella import has been removed;
`Colony.lean`, all procedure sources, and the existing `ListStateInvariant`
example match the task base (`git diff --exit-code` returned 0).
Research changes comprise the two historical reports and this new report.
The earlier follow-up's assertion that only two modules changed was inaccurate
at its recorded source state; that statement now explicitly includes the
historical umbrella change. Historical hashes/checks are retained as historical
evidence, not presented as the current source state.

SHA-256 of the checked sources:

| File | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `7c379b5cbde97f794ae9f841f5be5fad68136395ff0cb713d10bad686eefb6a5` |
| `lean/Colony/Examples/BoundedListProcess.lean` | `a09f3248a7779030ddf131953aedd781b68d4de667d3449e3958483779d67d48` |
| `lean/Colony/Examples/ListStateInvariant.lean` | `10746c7bc8ee2ce9ba403c269c994b4baa47fe45cccae61bf64715a52b9762e8` |
| `lean/Colony/Procedures/ListState.lean` | `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0` |
| `lean/Colony.lean` | `9a0b2cdeae4445542f4dc480c5994f35f760e81277a7c42648eb4db77f5355c0` |

## Commands and fresh results

Toolchain pin: `leanprover/lean4:v4.35.0` (`lean/lean-toolchain`).
`lake env lean --version` exited 0 and reported Lean 4.35.0,
`arm64-apple-darwin24.6.0`, commit
`eb6cafb7290e8bd5f2937522d8d804f58f02bafc`, Release.
Commands from `lean/`:

```sh
lake env lean --version
lake build Colony.Tactic Colony.Examples.BoundedListProcess Colony.Examples.ListStateInvariant Colony
lake env lean Colony/Examples/BoundedListProcess.lean
lake env lean Colony/Examples/ListStateInvariant.lean
```

All exited 0. Lake completed 11 jobs, rebuilding the changed umbrella and
replaying cached target results for the unchanged tactic and examples.
The two direct `lake env lean` checks elaborated their source files anew;
their imported modules were resolved through Lake's build artifacts.
The existing example emitted two unused-variable warnings; the full build
also replayed existing warnings in option/accumulator examples.
The fresh focused check printed:

```text
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=success
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=failure; state=restored; reason=colony: induction branch lacks a command constructor
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=failure; state=restored; reason=colony: induction branch lacks a command constructor
[Colony.listProcess] candidates=2; attempts=0; ambiguous command lists
'Colony.Examples.extended_process_preserves_list_state_invariant' depends on axioms: [propext, Quot.sound]
```

Commands from the repository root:

```sh
git diff --check
git diff --exit-code 702a19c205d6304b5a97eb81fb6876ef119e5567 -- lean/Colony.lean lean/Colony/Procedures/ lean/Colony/Examples/ListStateInvariant.lean
shasum -a 256 lean/Colony/Tactic.lean lean/Colony/Examples/BoundedListProcess.lean lean/Colony/Examples/ListStateInvariant.lean lean/Colony/Procedures/ListState.lean lean/Colony.lean
git diff 702a19c205d6304b5a97eb81fb6876ef119e5567 --name-only
git status --short
```

Each exited 0. The equality check produced no diff, hashes are listed above,
and the diff/status inventory showed only the scoped Lean and research changes
(including this untracked report). The report itself is excluded from its
source hash table to avoid self-reference.

## Bounded search and negative evidence

The unchanged positive theorem
`Colony.Examples.extended_process_preserves_list_state_invariant` assumes
`state.balance = state.recorded`, processes an arbitrary command list, then
executes `record 1` and `skip`. Its unchanged equality conclusion closes with
`by colony`. Neither the procedure definitions nor the statement/assumptions
were edited for this correction.

The specialized fallback counts command-list locals. Exactly one candidate
allows one structural induction, generalizing non-proposition locals. Each
branch uses `simp_all [process, step]` and `omega`, optionally splitting one
command local. Failed induction restores its saved tactic state and exits;
it cannot fall through to generic list/Nat induction. Two candidates cause
zero attempts. The bound is one candidate/induction attempt per invocation,
not a runtime or simplifier bound and not a limit on nil/cons obligations.

The focused source checks rejection of a false offset property, rejection of
an unsupported equality with an additional Nat local, and rejection of an
ambiguous two-list goal. Each uses `fail_if_success`, after which `trivial`
closes the surrounding `True`. The code's explicit save/restore and failure
traces record candidate rollback; the surrounding `fail_if_success` is also
transactional, so that wrapper alone is not a separate proof of rollback.
The concrete witness `[ListCommand.record 1]` from state `⟨0, 0⟩` computes
both counters to `1`; `decide` proves the negation of their differing by one.

## Failed attempts and import effects

The previous candidate's umbrella import exceeded scope and its report omitted
that change from its scope claim. Removing the import and building the focused
target explicitly corrects both issues without changing any Lean proof.
No new solver design was attempted in this correction. Earlier failed attempts
remain recorded in the historical reports: unpinned direct Lean/module lookup,
an interpreter invocation without `main`, generic induction fallthrough,
a proposition/Bool mismatch, unsupported prefix/initial-state theorem forms
(including an internal exception), and trace registration with
`builtin_initialize`. Those are historical observations, not newly rerun checks.

The umbrella no longer imports the focused example. The focused source imports
`Colony.Tactic` and the existing `Colony.Procedures.ListState` directly; the
tactic already imports `Std.Tactic` and `ListState`. No global simp attribute
was added. Success includes shared-import simplifier effects and explicitly
unfolds `process` and `step` using `simp_all`, followed by `omega`. It does not
demonstrate a solver independent of that environment. The focused trace option
stays local to that module and its checks are requested as a direct target.

## Assurance and limitations

The focused theorem is an ordinary Lean proof term with reported dependencies
`[propext, Quot.sound]`; these are existing Lean axioms, not new declarations.
No `sorry`, `admit`, new axiom, native evaluation axiom, or disabled kernel check
is introduced. Assurance is local elaborator/kernel acceptance on the pinned
Lean toolchain. These checks do not establish exported replay,
independent-kernel acceptance, correspondence to Cardano execution, a runtime
bound, or a performance improvement.

The evaluator and broader Python/JavaScript pilot checks were not run for this
Lean import correction. No evaluator, policy, benchmark, challenge, CI, or
protected file was edited. Existing unrelated linter warnings are left intact.
