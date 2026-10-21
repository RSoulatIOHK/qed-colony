# AUTO-abd0a5c138: bounded monotonicity chaining for ordered products

## Scope and acceptance (recorded before this revision)

Preserve the inherited `orderedProduct` definition and both positive theorem
statements in `lean/Colony/Examples/OrderedProduct.lean`, each proved with exactly
`by colony`. Replace duplicated rule-search code with a deterministic bounded
rule list, with no example identifiers or helper theorems in the tactic.
Check invalid/reversed hypotheses, non-vacuity, nested monotonicity, and the
search bound. Run the pinned Lean build, focused examples and axiom inspection.
Only the tactic, example, and this research evidence are in scope.

## Starting state

Requested base: `097a4117c7f7038f8d448217d7836a0d95d41bbe`.
Actual checkout HEAD: `09502b1adf179b8e83dcc2b2ac1a1be07f6b7e3d`.
The checkout included uncommitted edits to the tactic and ordered-product
example from the interrupted attempt. The committed example originally only
chained supplied inequalities; the inherited edits additionally tested natural
multiplication monotonicity. Neither inherited positive statement is changed.
The previous worker exceeded its 480-second limit; no proof conclusion follows
from that interruption.

Before new implementation, `cd lean && lake build Colony && lake env lean
Colony/Examples/OrderedProduct.lean` exited 0 (13 build jobs; unused-variable
warnings). This includes rejection checks written using `fail_if_success`.

## Rule and bound

The search tries `assumption`, then the fixed rules `Nat.mul_le_mul`,
`Nat.add_le_add`, and `Nat.le_trans`, in that order. Every failed rule restores
its tactic/metavariable snapshot. Each rule's premises use the same recursive
solver. No example names, ordered-product unfolding, local helper lemmas,
online service, or theorem-name dispatch is involved.

Fuel is exactly **4 rule applications per branch**. Fuel zero only attempts
`assumption`. These rules have two premises: an accepted tree has at most
15 internal rule applications and 16 assumption leaves (31 total nodes).
A conservative bound for recursive search invocations, including unsuccessful
candidates, is `T(0)=1`, `T(d)=1+6*T(d-1)`, hence `T(4)=1555`.
Lean's normal heartbeat limits additionally apply. This bound describes the
new order-search stage, not the existing fallback portfolio. The rule list
is deliberately finite and restricted to natural-number inequalities.

## Focused results

Pinned setup: `leanprover/lean4:v4.35.0`, with no added dependencies.

- `cd lean && lake build Colony`: exit 0, 13 jobs, existing linter warnings.
- `cd lean && lake env lean Colony/Examples/OrderedProduct.lean`: exit 0 for
  the final example source, with unused-variable warnings.
- The unchanged `orderedProduct_chain` and inherited
  `orderedProduct_mul_chain` both close with exactly `by colony`.
- `orderedProduct_nested` closes with four nested multiplication/addition rule
  applications. `orderedProduct_distractor` checks an irrelevant order fact.
  Both also use exactly `by colony`.
- Both reversed-hypothesis checks compile with `fail_if_success`; neither
  invalid goal is accepted. The explicit counterexample
  `¬ (orderedProduct [] * 2 ≤ orderedProduct [] * 1)` compiles by `decide`.
- The positive assumptions have a concrete nonzero model using lists
  `[2]`, `[3]`, `[4]`, `[5]` and factors `2 ≤ 3`, checked by `decide`.
- All four named positive declarations print `does not depend on any axioms`
  through `#print axioms`. This is Lean elaborator/kernel acceptance and an
  axiom dependency inspection, with no exported or independent kernel replay.
- `node --check observatory/dist/app.js`: exit 0.
- `git diff --check`: exit 0.

Final source SHA-256 values (uncommitted overlay on the actual HEAD above):

```text
lean/Colony/Tactic.lean
94c1433fc14c739ba3055ee55ddb60e99d11e577badab3736eac7157f0a9c840
lean/Colony/Examples/OrderedProduct.lean
3ffbd8b804c1670bf9a6d6dde9b3a944aae91c1a2db4d5362a339309d19a743b
```

## Failed attempts and broader checks

- Inherited interruption: prior worker exceeded 480 seconds. The initial
  focused rerun in this worker passed; the timeout is not a proof rejection.
- The example checks that `omega`, `simp_all <;> omega`, and `decide` alone
  each fail on the unchanged nonlinear product-chain goal. Each expected
  failure is verified with `fail_if_success` in the compiling example.
- One edit command used a repository-relative path while already inside
  `lean/`, so its Python read failed with `FileNotFoundError`. It changed
  nothing. The corrected edit and final focused Lean check succeeded.
- `python3 scripts/evaluate_lean.py --no-build --strategies colony --output
  research/experiments/AUTO-abd0a5c138-evaluator.json`: exit 2. It observed
  individual process errors/timeouts, then rejected the run with
  `Sources changed during evaluation; rerun from a stable checkout`, because
  this worker edited the example during that run. No evaluator report was
  accepted or retained; no benchmark score is claimed.
- `python3 -m unittest discover -s tests -v`: exit 1, 335 tests in
  232.040 seconds, **3 failures and 13 errors**. The errors were permission
  denials for subprocess `ps` or HTTP socket binding. The failures were
  `test_unverifiable_cleanup_keeps_process_record_and_worker_slot`,
  `test_compiler_audit_rejects_term_style_proof_def_in_different_namespace`,
  and `test_actual_triage_outage_reconnects_after_restart_and_replays_completed_handoff`.
  The compiler-audit test received empty output instead of its expected helper
  diagnostic; its cause was not established. No controller/test changes were
  attempted. This run does not establish a green full-suite regression check.

## Limitations

This proves composition of supplied natural-number inequalities and nested
monotonicity on opaque product expressions. It does not derive inequalities
from elementwise relations on lists. Rule choices backtrack; assumption
choices do not exhaustively backtrack. Fuel exhaustion is inconclusive,
not evidence that a theorem is false. The existing fallback portfolio can
solve goals outside this search bound. There is no performance comparison,
exported replay, independent-kernel result, or Cardano correspondence claim.
Only the tactic, its distinct example, and this evidence were edited.
No commit or publication was performed.
