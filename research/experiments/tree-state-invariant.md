# Bounded tree-state invariant probe

## Scope and acceptance

Task `AUTO-40be63f767`: prove the unchanged
`execute_preserves_tree_state_invariant` with `by colony`, reject the false offset
control, preserve the original goal after candidate failure, and retain the
existing positive and non-vacuity examples. No benchmark, challenge, evaluator,
policy, or CI files are changed.

The inherited candidate uses a binary `CommandTree` whose root command and both
subtrees execute in order, threading two natural-number counters. Commands add
the same amount to both counters. Exactly one eligible `CommandTree` local is
required for the new tactic branch. Other non-propositional locals are
generalized; dependent hypotheses are reverted by Lean's induction tactic.
The fixed branch unfolds execution, applies the right then left induction
hypothesis, splits the root command, and closes using simplification and
`omega`. It performs no recursive tactic search. A saved tactic state plus
`withoutRecover` ensures a failed candidate throws and restores its goals and
metavariable assignments. Local identity is compared by `fvarId` when choosing
which locals to generalize.

The original theorem statement and false control are unchanged. Additional
examples check execution of a populated tree, an inhabited invariant
precondition, unequal counters without that precondition, and a concrete
counterexample to the false offset claim. `Colony.lean` imports the example.

## Exact tested sources

- Requested base revision: `3a7c71e41ba1a29df363e8847fbe5a01e3a96bf8`.
  The tree model and example did not exist at that revision.
- Actual parent revision: `398319612c9cce4a264a1853d06cad3c85c8f197`.
- Existing branch: `codex/colony-auto-40be63f767-74850e419bca`.
- This retry began with uncommitted changes to the tree model, tactic, and report,
  plus the focused check file. The recursive state-threading model and fixed IH
  application branch were inherited from that attempt. They were verified here;
  this retry adds concrete controls and broader focused checks.
- No commit or publication was performed. Identify the tested candidate by the
  parent revision and these SHA-256 content hashes:

| File | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `f2fa36e5934e29ef25f5f31b5e587c768f36bf5be5960eb436c8819149eff712` |
| `lean/Colony/Procedures/TreeState.lean` | `1c74d0c8c7aad09bb6518f148e3f8f8fd59d3d40a7ad5a3c9ea1f27f27783ad4` |
| `lean/Colony/Examples/TreeStateInvariant.lean` | `daa9ff5b004daaade268b31821485d730f12aad280018a1875985639b8335389` |
| `lean/Colony.lean` | `bf244717d1de65ea66b347a69ed76ffaed075abf76768bd4f3f296c546e9e01f` |
| `research/experiments/tree-state-invariant-check.lean` | `7c5a9b2a4182162e1bdfb87a24e29eeee8d4f9d7cef6125f7ab3e14e783a11e4` |

## Commands and results

Lean commands run from `lean/`; other commands run from the repository root.

- `lake env lean --version`: Lean 4.35.0, toolchain commit
  `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`, Release.
- `lake build Colony SeedProofs`: passed, 14 jobs, both before and after the
  retry's tactic/example changes. The invariant, its false control, existing
  imported examples, and seed positive/non-vacuity cases elaborate. Existing
  unused-variable and unnecessary-`simpa` linter warnings remain.
- `lake env lean ../research/experiments/tree-state-invariant-check.lean`:
  final run passed. Checks reject each pre-induction portfolio tactic and the
  naive induction/simplification shape on the target before `colony` proves it.
  An irrelevant tree local forces the tree candidate to fail, then the later
  reverse-accumulator bridge proves the restored original goal. Two tree locals
  disable the candidate. A known extra-dependent-hypothesis boundary is checked
  with `fail_if_success`, followed by an explicit application of the accepted
  invariant theorem. Axiom reports for both the invariant and rollback theorem
  are exactly `[propext]`.
- `lake env lean Colony/Examples/BoolStateTransition.lean`: passed; its invariant
  reports `[propext]`.
- `lake env lean Colony/Examples/NestedResultTransition.lean`: passed.
- `node --check observatory/dist/app.js`: passed.
- `python3 -m unittest discover -s tests -v`: ran 286 tests; failed with 2
  failures and 13 errors. Process-launch tests encounter sandbox denial of `ps`;
  five server tests encounter denied socket binding. Two assertion failures
  concern missing process evidence and `needs_review` versus `waiting_network`.
  These components are outside this task's edit scope; no full-suite pass is
  claimed. Resource warnings about unclosed test databases also appeared.
- `git diff --check`: passed.
- The evaluator command that writes `artifacts/benchmark-results.json` was not
  run: benchmark artifacts are outside the authorized edits. No score or
  performance claim is made.

## Failed candidate shapes and limitations

- The inherited report describes an earlier weight-only model that added a
  recursively computed weight to both counters. Simplification could prove its
  invariant without induction, so it was inadequate evidence for this probe.
  The inherited retry uses genuine recursive state threading instead. No
  benchmark theorem or definition from the requested base was changed.
- Naive `induction tree generalizing state` followed only by
  `simp_all [execute, applyCommand]` and `omega` fails to instantiate both
  subtree hypotheses at intermediate states. This failure is reproduced by a
  guarded check. The fixed IH application sequence closes the required theorem.
- The inherited attempt reported that Lean tactic recovery could mask candidate
  errors. The branch runs under `withoutRecover`; its fallback regression now
  passes and its resulting proof has no synthetic-proof axiom dependency.
- During this retry an additional `(n : Nat)` and hypothesis
  `hn : n = state.leftCount` caused the fixed IH applications to leave additional
  intermediate-state obligations; the initial focused check exited 1 at that
  example. This is a deliberate scope boundary, now guarded as expected failure.
  Generalization is implemented, but arbitrary extra dependent hypotheses are
  not guaranteed to be solved by this small portfolio.
- The earlier report mentioned a focused check run before its imported `.olean`
  existed. This retry waits for the build before running that check.

## Assurance

Lean 4.35.0 elaboration and kernel checking accepted the invariant's ordinary
proof term. `#print axioms` reports only Lean's standard `propext`, with no
`sorryAx`, custom axiom, native evaluation axiom, or disabled kernel checks.
The guarded negative tests establish tactic rejection for those inputs;
concrete counterexamples additionally establish that the false offset target
is invalid and the precondition is necessary. This is local elaborator/kernel
acceptance only: no exported replay, independent kernel, or correspondence to
Cardano execution was established. Publication remains for the controller.
