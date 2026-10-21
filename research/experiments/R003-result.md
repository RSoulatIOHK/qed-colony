# R003: reverseAcc library adapter experiment

Task: `AUTO-f979817a4a`. Scope and acceptance are the bounded R003 proposal,
its review, and this task's stricter requirements: at most one bridge, one
deterministic rewrite branch, three candidate scripts, unchanged original
frontier, protected definitions, evaluator, axiom policy, and 15-second /
200,000-heartbeat case limits. Stop on proof failure or regression; no expanded
search or specification changes.

## Source identity and implementation

Base revision: `0e48a058b97fd4288d7562029d790009561d3d37`.
The controller first published the tested Lean sources in candidate revision
`e311fc8540840fb8e01d28d3fc3367922955c4f1`. The recorded checks ran before
that commit, against the uncommitted source snapshot described below. The two
edited Lean file hashes in that snapshot match the files in this published
candidate exactly. This provenance correction changes only this research note;
the current PR head is recorded by GitHub rather than embedded in its own file.
The two Lean edits were already present, uncommitted, when this continuation
started. They were retained and checked, not attributed to new work in this
continuation. The worker performed no commit or publication. The exact tested source
snapshot is identified by `source_sha256` in [the complete evaluator report](R003-evaluator.json),
including hashes of both edited Lean files and all protected/evaluator inputs.
Edited source SHA-256 values:

- `lean/Colony.lean`: `574aff076baaeca2ad80ec598ff990b41dbb65b34268b2a8a826333001d41e82`
- `lean/Colony/Tactic.lean`: `6b30bfc557287175b11cb1b4a2944234a66299f607e6bdc6ec628edb5662fbed`

`Colony.reverseAcc_bridge` in `lean/Colony.lean` proves
`∀ (xs acc : List Nat), Colony.Seed.reverseAcc xs acc = xs.reverse ++ acc`.
The single candidate script uses structural induction on `xs`, generalizes
`acc`, and simplifies the defining equations, induction hypothesis,
`List.reverse_cons`, and `List.append_assoc`. No other bridge candidate was
tried in this continuation; none failed. Prior controller feedback reports that
the earlier author attempt exceeded its 480-second worker wall limit; that is
not evidence of a Lean proof failure or success.

The single added branch in `colony`, after arithmetic and Boolean splitting,
uses `simp only` with the bridge, `List.append_nil`, and
`List.reverse_reverse`. It restores the initial tactic state on failure before
the existing induction fallback. The bridge is resolved by name at tactic
execution because the protected Seeds module itself imports the tactic.

**Library exposure and attribution.** The bridge deliberately lives in the
shared `Colony` import, after Seeds; it has no `[simp]` attribute and does not
enter the global simp set. Every unchanged evaluator strategy imports exactly
the same `Colony` module and can refer to `Colony.reverseAcc_bridge` explicitly.
Thus baselines receive the same theorem and defining equations. Their fixed
scripts receive no extra lemma hint; the colony branch supplies that hint.
This is library augmentation plus a specific adapter branch, not general
accumulator normalization or a fair hinted-baseline performance comparison.

## Checks and resources

Toolchain pin: `leanprover/lean4:v4.35.0`. Actual compiler:
`Lean (version 4.35.0, arm64-apple-darwin24.6.0, commit eb6cafb7290e8bd5f2937522d8d804f58f02bafc, Release)`.

- `lake build`: exit 0, eight jobs; includes existing Boolean examples and seed
  proofs.
- Direct `lake env lean -DmaxHeartbeats=200000 Colony.lean`: exit 0 in
  4.700368 seconds with a 15-second subprocess deadline. This recompiles the
  actual bridge declaration. `#print axioms Colony.reverseAcc_bridge` reports
  exactly `[propext]`. Commands and results: [bridge checks](R003-bridge-checks.json).
- `python3 scripts/evaluate_lean.py --output research/experiments/R003-evaluator.json`:
  exit 0, all 40 rows completed. The evaluator validated the unchanged manifest,
  protected definitions and challenge lock both before and after evaluation;
  all recorded source hashes also matched a final read of the checkout.
  Colony certified all eight positives (including the recursive and payment
  non-vacuity cases), plus the original unsupported frontier. The false
  `false_shared_payment_safety` failed ordinarily, with both
  `shared_payment_attack_witness` and `allocated_payments_nonvacuity` certified.
  There were zero timeouts and zero evidence errors across all four strategies.
  Unhinted baseline positives were simp 4/8, omega 1/8, grind 1/8; each failed
  the frontier. These are observations from the fixed scripts, not superiority
  claims.
- The exact evaluator declaration `benchmark_reverse_involution_frontier`,
  with unchanged statement
  `∀ (xs : List Nat), reverseAcc (reverseAcc xs []) [] = xs`
  and proof script `by colony`, was accepted in 3.216708 seconds under the
  unchanged 15-second / 200,000-heartbeat limits. Its exact `#print axioms`
  output is `'benchmark_reverse_involution_frontier' depends on axioms: [propext]`.
  The report retains its statement and generated-source hashes and compiler
  output. All 40 row wall times ranged from 2.704329 to 12.323739 seconds.
- `python3 -m unittest discover -s tests -v`: exit 1; 146 tests in 41.652
  seconds, 139 passed and seven errors. Three `test_execute_job` cases were
  denied `ps`; four `test_server` cases were denied socket binding by the
  sandbox. Evaluator tests passed. No unrelated code was changed to address
  these environment limitations.
- `node --check observatory/dist/app.js`: exit 0.
- `git diff --check`: exit 0.

Wall times include startup/imports and are observations, not statistical
performance claims. No exact heartbeat consumption was instrumented; successful
bounded checking establishes only that the configured limit was not exceeded.

## Assurance

The bridge and the exact original frontier declaration have ordinary Lean
elaboration/kernel acceptance, each with transitive axiom dependency
`[propext]`, within the existing allowlist. No exported replay,
independent-kernel acceptance, or Cardano correspondence is claimed. The local
pilot trusts its evaluator, compiler, manifest, and challenge lock; it is not a
tamper-proof security boundary.
