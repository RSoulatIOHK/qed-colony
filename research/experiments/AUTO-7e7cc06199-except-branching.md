# AUTO-7e7cc06199: bounded `Except` branching

## Scope and acceptance

Try eligible local `Except ε α` declarations in deterministic context order,
splitting exactly one candidate into its two constructors per attempt. Require
all branches to close; on failure restore the complete tactic snapshot before
trying the next candidate. No recursive branching or new procedures module.
Check the transition invariant, unchanged failure state, failed-candidate
restoration, false-target rejection, and Boolean/Option/ListCommand regressions.

## Source and implementation

Requested base: `b9a946a3953fc55e7da19c0fd5d3f66a3193dd39`.
Continuation HEAD: `3cff672fafdf047a9f8384d8e9974b16297f2f68`, on the existing
`codex/colony-auto-7e7cc06199-c1dcb89b631e` branch. At entry, the Except
fallback and aggregate import were already committed; Tactic/ResultFlow had
additional uncommitted edits (including restoration of the subtraction theorem),
and an untracked prior build log existed. This continuation retained and checked
those changes, added bound/partial-branch/non-vacuity regressions and documentation,
and corrected the earlier note. No commit or publication was performed.

`exceptPortfolio` splits one candidate and runs `simp_all; omega`,
`simp_all; decide`, or `omega`, each required to solve its goal. An additional
empty-goal check precedes proceeding to the next branch. The caller restores
`saveState` on any exception; no split survives to the next candidate. The
fallback follows Option branching and precedes ListCommand branching.

`@[simp] applyResult` remains unchanged: `.ok amount` adds `amount` to both
natural counters, while `.error _` returns exactly the input pair. The original
subtraction statement is retained, with no equality assumption:

```lean
(state : Nat × Nat) (result : Except String Nat) :
(applyResult state result).1 - (applyResult state result).2 = state.1 - state.2
```

The existing equal-counter theorem is also retained unchanged:

```lean
(state : Nat × Nat) (result : Except String Nat) (h : state.1 = state.2) :
(applyResult state result).1 = (applyResult state result).2
```

Both close with `by colony`. `except_after_failed_candidate` explicitly checks
that the first, irrelevant split cannot solve the target, before `colony`
restores that failed attempt and succeeds on the later candidate. Guards also
reject the false counter-offset target and a match whose error branch is true
but whose ok branch is false. `two_results_need_two_splits` is a true target
rejected by `colony`, then proved by explicit cases: it checks the one-split
bound. Concrete success, failure, and false-offset counterexamples use `decide`.
No existing theorem statements, assumptions, definitions, or bounds changed.

Final source SHA-256:

- `lean/Colony/Tactic.lean`: `b1240c489c7d5df6081e0d69faa4f5bca0d8f4e27221e4043db2cdb5fe2ec13e`
- `lean/Colony/Examples/ResultFlow.lean`: `ef804614cf5cfda22ecf2f8d781003ba03c65434b38641f36b921dd142a8065c`
- `lean/Colony.lean` (existing import retained): `e9db9f0b955692315edb85a73922540b1108a1ec18570a1c0117d3164879e9d3`

## Commands and results

- `cd lean && lake build`: initial checkout exit 0; final implementation exit 0,
  12 jobs, including Boolean, Option, ListStateInvariant (ListCommand),
  ResultFlow, Colony, and SeedProofs. Unused-variable warnings remain.
- `cd lean && lake env lean --version`: Lean 4.35.0, compiler commit
  `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`, matching the toolchain pin.
- Axiom inspection, exit 0, exact command:

```sh
cd lean
lake env lean --stdin <<'LEAN'
import Colony.Examples.ResultFlow
#print axioms Colony.Examples.result_preserves_counter_difference
#print axioms Colony.Examples.successful_result_updates_counters_consistently
#print axioms Colony.Examples.failed_result_leaves_state_unchanged
#print axioms Colony.Examples.except_after_failed_candidate
#print axioms Colony.Examples.two_results_need_two_splits
LEAN
```

Outputs respectively: `[propext, Quot.sound]`, `[propext]`, no axioms,
`[propext]`, `[propext, Quot.sound]`. No arbitrary or native-evaluation axioms.

- `python3 -m unittest discover -s tests -v`: exit 1; 286 tests in 74.500s,
  two failures and 13 errors. Eight error/subtest entries report denied `ps`;
  five report denied socket binding. Assertion failures are
  `test_unverifiable_cleanup_keeps_process_record_and_worker_slot` and
  `test_actual_triage_outage_reconnects_after_restart_and_replays_completed_handoff`.
  These controller failures were not repaired or independently diagnosed here.
- `python3 scripts/evaluate_lean.py --no-build --output research/experiments/AUTO-7e7cc06199-evaluator.json`:
  exit 0; all 40 unchanged strategy/case rows completed with zero timeouts and
  zero evidence errors. Colony accepted 8/8 positives and the existing frontier;
  the false target was rejected with its positive witnesses accepted. The
  evaluator verified the unchanged protected-source/challenge lock. All report
  source hashes were checked against the final checkout. The output location
  stays within the authorized research scope; `--no-build` uses the successful
  full build above. See [complete report](AUTO-7e7cc06199-evaluator.json).
- `node --check observatory/dist/app.js`: exit 0.
- `git diff --check`: exit 0.

## Failed attempts

The prior note reported abandoning the subtraction theorem for an equal-counter
invariant. That substitution is not the final result: the original subtraction
statement is now retained and accepted by `colony`. Earlier import/simp failures
were reported in that note but were not reproduced in this continuation. Prior
review feedback reports a worker wall-time limit, not a proof-checking result.

An actual failing command in this continuation was `cd lean && lake build`
while the new two-result bound regression ended with
`cases first <;> cases second <;> decide`. Lean rejected all four branches with
"Expected type must not contain free variables": constructor payload locals
remained in the match expressions. Replacing only that explicit regression
proof's final `decide` with `simp` closed the reduced branches. The theorem,
tactic search, and bounds were unchanged; the next build passed.

## Assurance and limits

Only Lean elaborator kernel acceptance is claimed. All successful proofs are
ordinary Lean proof terms checked by the pinned local compiler; exit codes alone
are not certificates. No exported replay, independent-kernel acceptance,
Cardano execution correspondence, completeness, or performance claim is made.
The local pilot still trusts its compiler, evaluator, manifest, and challenge lock.
