# AUTO-7e87e900e8: bounded command-list fallback, review follow-up

## Scope and acceptance

Base revision: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
Starting revision for this follow-up: `e4476f7b093b3d31655f4318aa7e19c04e7e8af8`.
This report supersedes the bound and theorem claims in
`AUTO-7e87e900e8-bounded-list-process.md`. At the checked state recorded here,
the experiment changed `Colony.Tactic`, the focused `BoundedListProcess`
example, and the umbrella `Colony.lean` import list. That umbrella change
exceeded the task's module scope. The subsequent correction and fresh checks
are recorded in `AUTO-7e87e900e8-bounded-list-scope-correction.md`.
The procedure's
`ListCommand`, `step`, and `process` definitions and the existing
`ListStateInvariant` example are unchanged.

The positive theorem is a distinct multi-command statement: after processing
an arbitrary list from a state whose counters agree, it executes `record 1`
and `skip`, and the resulting counters still agree. Its proof script is exactly
`by colony`; no theorem statement, assumption, definition, or bound was changed
to make it close.

## Bounded behavior observed

With `trace.Colony.listProcess` enabled in the focused example, the pinned Lean
toolchain reported:

```text
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=success
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=failure; state=restored; reason=colony: induction branch lacks a command constructor
[Colony.listProcess] candidates=1; attempts=1
[Colony.listProcess] attempt=1; result=failure; state=restored; reason=colony: induction branch lacks a command constructor
[Colony.listProcess] candidates=2; attempts=0; ambiguous command lists
```

These four traces correspond to the positive theorem, the false `+ 1`
property, an unsupported property with an additional Nat local, and an
ambiguous two-list goal. Each failed `have` is wrapped in `fail_if_success`,
after which `trivial` closes the original `True` goal. The tactic saves its
state before the sole induction attempt and restores it in the failure handler.
For any goal containing a `List ListCommand` local, it now exits with an error
after that attempt fails, or after detecting multiple candidates. It does not
enter the later generic list/Nat induction loop. The bound is **one candidate
and one induction attempt per invocation**, not a bound on the structural
induction's nil/cons obligations, simplifier work, or total runtime. The trace
reports branch outcomes; it is not a performance measurement.

The intentionally false neighboring `+ 1` property is refuted concretely by
processing `[ListCommand.record 1]` from `⟨0, 0⟩`: both counters become `1`,
so they cannot differ by one. `decide` proves that negation, and
`fail_if_success` confirms `colony` does not prove the universal false claim.

## Reproduction and source identity

Toolchain: `leanprover/lean4:v4.35.0` from `lean/lean-toolchain`; `lake env lean
--version` reported Lean 4.35.0, commit `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`.
Commands were run from `lean/` except `git diff --check` and `shasum`:

```sh
lake env lean --version
lake env lean Colony/Examples/BoundedListProcess.lean
lake build Colony.Tactic Colony.Examples.BoundedListProcess Colony.Examples.ListStateInvariant Colony
git diff --check
shasum -a 256 lean/Colony/Tactic.lean lean/Colony/Examples/BoundedListProcess.lean lean/Colony/Examples/ListStateInvariant.lean lean/Colony/Procedures/ListState.lean lean/Colony.lean
```

The direct Lean check exited 0 and printed the traces above. The build exited
0, completing 11 jobs including both list-state examples and the umbrella
module. `git diff --check` exited 0. Existing linter warnings in unrelated
examples remain. The theorem's `#print axioms` result was:

```text
'Colony.Examples.extended_process_preserves_list_state_invariant' depends on axioms: [propext, Quot.sound]
```

SHA-256 of the checked source files:

| File | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `7c379b5cbde97f794ae9f841f5be5fad68136395ff0cb713d10bad686eefb6a5` |
| `lean/Colony/Examples/BoundedListProcess.lean` | `a09f3248a7779030ddf131953aedd781b68d4de667d3449e3958483779d67d48` |
| `lean/Colony/Examples/ListStateInvariant.lean` | `10746c7bc8ee2ce9ba403c269c994b4baa47fe45cccae61bf64715a52b9762e8` |
| `lean/Colony/Procedures/ListState.lean` | `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0` |
| `lean/Colony.lean` | `cb59a4ead3920f830e636d2bef14350b99a64c8e644fb07cb1d648fad7496dff` |

## Failed attempts and limits

- The starting candidate bounded its specialized helper but let a failed or
  ambiguous command-list goal fall through to generic list/Nat induction.
- The first edit returned a proposition for `hasCommandList`; Lean could not
  synthesize its `Decidable` instance at the use site. Converting it to a Bool
  with `decide` fixed the build.
- A new prefix form, `process (record amount :: skip :: commands) state`, and
  then an initial-state form, `process commands (step (step state ...) skip)`,
  failed in the specialized solver. The latter emitted `internal exception #5`
  in the trace. Those forms are not claimed as supported.
- Initial trace registration with `builtin_initialize` did not expose the
  trace option to an imported example. `initialize` did; the final trace and
  source use that registration.

At this historical checked state, `Colony.lean` imported the focused example,
so enabling the trace there also printed these diagnostics during the umbrella
build. The scope correction removes that import. No global simp
attribute was added. The helper explicitly runs `simp_all` with `process` and
`step`, while existing shared imports include `Std.Tactic` and its available
simplifier lemmas. The success therefore measures this exact imported
environment, including those simplifier effects.

The proof is an ordinary Lean term accepted by elaboration and Lean's kernel
with the axiom dependencies reported above. The checks do not establish
exported replay, independent-kernel acceptance, runtime guarantees, or
correspondence to Cardano execution.
