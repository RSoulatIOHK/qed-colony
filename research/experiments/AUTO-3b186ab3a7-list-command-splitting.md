# AUTO-3b186ab3a7: bounded splitting on `ListCommand`

## Scope and acceptance criteria

Add a deterministic fallback to `by colony` that selects at most one eligible
`Colony.Procedure.ListCommand` parameter, splits its constructors, and restores
the tactic state if the candidate fails. Prove the unchanged one-step invariant
under the unchanged assumption `state.balance = state.recorded`; reject an
intentionally false one-step equality. Existing Boolean branching and list-state
examples must elaborate.

## Changes

`Colony.Tactic` scans the local context in declaration order. At the first
non-implementation-detail local whose weak-head-normalized type is
`Colony.Procedure.ListCommand`, it saves tactic state, performs `cases`, and
tries `simp_all [Colony.Procedure.step] <;> omega` on every generated branch.
If the candidate fails, it restores the saved state and ends this fallback
without trying another command parameter. The new example proves

```lean
(step state command).balance = (step state command).recorded
```

from the original equality assumption using `by colony`. A neighboring
`fail_if_success` example checks that adding `1` to the recorded result is not
proved. `ListCommand`, `step`, and the theorem assumptions and conclusion are
unchanged.

## Failed approaches

The original failed build logs and uncommitted source revisions were not
retained. The following are fresh reproductions from Git revision
`3d24cd72736d84b534c3c10d3252f334fbdd65c9`. Each used an otherwise
unchanged copy of the `lean/` project, with only the indicated replacement for
the branch solver in `Colony/Tactic.lean`. The example source had SHA-256
`935390dffe312a90fa316bb798cfde13e71c5e46cef338cb3b060de079bb8822`.

| Reproduced source revision | Branch solver after `cases` | Exact command and exit | Lean diagnostic |
| --- | --- | --- | --- |
| Git revision above; `Tactic.lean` SHA-256 `10be43afcc65ac436a48ab8769e8d9f2e671cbca15426fa676b32524039b3889` | `arithmeticPortfolio` | `lake build Colony` from the project copy; exit 1 | `error: Colony/Examples/ListStateInvariant.lean:13:2: colony: the initial proof portfolio could not close this goal` |
| Git revision above; `Tactic.lean` SHA-256 `118abdafcc157627ca95f9ffb6227f97e5b10b16ffa0c4d32933ced4bfda5841` | `simp_all [Colony.Procedure.step]` as a separate tactic, then `arithmeticPortfolio` | `lake build Colony` from the project copy; exit 1 | `error: Colony/Examples/ListStateInvariant.lean:13:2: colony: the initial proof portfolio could not close this goal` |

In both reproductions, Lake reported `Some required targets logged failures:`,
`- Colony.Examples.ListStateInvariant`, and `error: build failed`. The tactic
restores state after the branch solver fails, so the build diagnostic reports
the final portfolio failure rather than the internal branch failure. Splitting
with arithmetic alone did not expose `step` to simplification; running
`simp_all` separately did not make the full branch solver succeed. The final
branch solver combines `simp_all [Colony.Procedure.step] <;> omega` inside
`solve`.

## Lean check and assurance

- Source revision: Git `3d24cd72736d84b534c3c10d3252f334fbdd65c9`;
  `Tactic.lean` SHA-256
  `d193f91238ab9d7a49856df2430588b56246fafd73f8036015b0facf47002a88`.
- Exact command: `lake build Colony` from a fresh copy of the `lean/` project
  without `.lake/`; exit 0. Lake reported
  `Build completed successfully (8 jobs).` It built
  `Colony.Procedures.ListState`, `Colony.Tactic`,
  `Colony.Seeds`, `Colony.Examples.BooleanBranching`,
  `Colony.Examples.ListStateInvariant`, and `Colony`.
- Toolchain: `leanprover/lean4:v4.35.0` from `lean/lean-toolchain`;
  `lake --version` in the project reported
  `Lake version 5.0.0-src+eb6cafb (Lean version 4.35.0)`.
- Lean diagnostics: no errors. The only warnings were:

  ```text
  warning: Colony/Examples/ListStateInvariant.lean:15:9: Variable name `state` is not explicitly referenced.
  warning: Colony/Examples/ListStateInvariant.lean:15:29: Variable name `command` is not explicitly referenced.
  ```

  They concern the parameters in the intentionally false `fail_if_success`
  check. This check and the existing Boolean branching and list-state examples
  elaborated.
- Assurance: Lean elaborator kernel acceptance for this build. This is not a
  claim of exported replay, independent-kernel acceptance, or correspondence
  to Cardano execution. No performance or benchmark superiority is claimed.
