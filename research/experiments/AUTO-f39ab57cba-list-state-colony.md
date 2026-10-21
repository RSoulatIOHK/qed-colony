# AUTO-f39ab57cba: list-state invariant with `colony`

## Scope and source

Requested base revision: `10b6ba7bd1b2070ac0af8616a4d745c22e698a4e`.
Starting checkout revision: `1db3de0c92073e544f337ad7f48d005d89ca7dd4`.
This experiment is an uncommitted working-tree change on that checkout. The
project pins `leanprover/lean4:v4.35.0`.

Acceptance target: the unchanged `process_preserves_list_state_invariant`
theorem closes with `colony`; the embedded intentionally false target remains
rejected; the Boolean and arithmetic examples still elaborate. No procedure,
theorem statement, assumption, bound, challenge, or evaluator was changed.

## Tactic change and attempts

The existing arithmetic and Boolean candidates run first. The structural
induction candidate now recognizes a `List ListCommand` local, generalizes the
other locals, and inducts on the list. In the cons case it unfolds `process`,
applies the induction hypothesis, then splits `ListCommand` into `record` and
`skip`. Simplification of the original `process` and `step` definitions and
`omega` close the resulting obligations. The branch is deterministic and uses
ordinary Lean tactics.

Failed attempts during this experiment:

1. At starting revision `1db3de0`, `lake build Colony` failed at the unchanged
   theorem with `colony: the initial proof portfolio could not close this goal`.
   The existing induction simplified the recursive call before splitting the
   arbitrary command.
2. The first new induction script used quoted short identifiers `[process]` and
   `[step]`. `lake build Colony` failed with `simp_all made no progress` and
   `` `simp` made no progress ``. The tactic quotation gave those identifiers
   hygiene scopes, so they did not refer to the procedure definitions.
3. Writing qualified names literally inside that quotation failed with
   `Unknown identifier Colony.Procedure.process✝`. Constructing explicit
   `Colony.Procedure.process` and `Colony.Procedure.step` identifiers for
   antiquotation resolved the name issue. The diagnostic logging used to find
   this was removed.

## Check and assurance

From `lean/`, the final command was:

```sh
lake build Colony
```

Result: exit code 0, `Build completed successfully (8 jobs)`, including
`Colony.Tactic`, `Colony.Examples.BooleanBranching`,
`Colony.Examples.ListStateInvariant`, and `Colony`. The list-state example
contains the unchanged theorem proved by `colony` and a `fail_if_success`
negative control for the false equality. The Boolean example includes two
branching theorems, an arithmetic regression theorem, and its own negative
control. Their successful elaboration is evidence for these checks; the build
exit code alone is not a separate proof certificate.

Assurance: **Lean elaborator kernel acceptance only** on the pinned toolchain.
No exported replay, independent-kernel acceptance, or correspondence to
Cardano execution was checked. The procedure is a small synthetic model.
