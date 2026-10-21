# REPAIR-6f8bb7190374428aa34891f1645c10ed: bounded ListCommand induction

## Scope and source

Starting source revision: `d164a8fc9aad14363d8a777b21e7d2a45596046b`.
Reference implementation inspected: `025dcddfe41e39d3d7703e7366aeabdf6e93c459`
(PR 30). The reference is source material; this record describes a fresh
experiment on the starting revision. Only the authorized Lean and research
paths were changed. The theorem statement, procedure definitions, assumptions,
and bounds are unchanged.

## Attempted tactic change and failed attempt

Added one deterministic structural-induction special case in `colony` for a
local of type `List ListCommand`. It generalizes the other locals, inducts on
the command list, simplifies the empty case with the existing `process`
definition, and in the cons case unfolds `process`, applies the induction
hypothesis, splits the command constructor, and uses `simp_all` with the
existing `step` definition and `omega`. Other list and natural induction goals
continue through the pre-existing generic branch. This uses ordinary Lean
proof tactics and adds no axioms or evaluation shortcut.

The first attempted build, after adding that branch but before correcting the
example proof body, was:

```sh
cd lean && lake build Colony
```

It failed because `ListStateInvariant.lean` contained a `fail_if_success`
wrapper whose purpose was to assert that `colony` could not prove the invariant.
With the new branch, the tactic succeeded and that stale assertion failed. I
then changed only the proof body of the unchanged theorem to `by colony`; the
intentionally false target retains its negative `fail_if_success` check.

## Check and result

Final command (run from `lean/`):

```sh
lake build Colony
```

Result: exit code 0; `Build completed successfully (8 jobs)`. The build output
showed `Colony.Tactic`, `Colony.Examples.BooleanBranching`,
`Colony.Examples.ListStateInvariant`, and `Colony` built successfully. The
unchanged `process_preserves_list_state_invariant` theorem is now proved by
`colony`. The intentionally false equality remains rejected by its
`fail_if_success` control. The existing Boolean branching and arithmetic
regressions elaborate in `Colony.Examples.BooleanBranching`.

Assurance: **Lean elaborator kernel acceptance only** on the repository-pinned
Lean toolchain. No exported replay, independent-kernel check, or correspondence
to Cardano execution was established. The successful build is the recorded
elaboration result, not a separate proof certificate.
