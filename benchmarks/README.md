# Colony seed benchmark

This is a pipeline smoke test with eight positive unit cases, one intentionally false property, and one true frontier goal. It is not the proposed public Plutus Gauntlet and does not establish complex Cardano verification or outperformance of any prover.

Run from the repository root:

```sh
python3 scripts/evaluate_lean.py --output artifacts/benchmark-results.json
python3 -m unittest tests/test_evaluate_lean.py -v
```

The evaluator builds the pinned Lean 4.35.0 project in `lean/` and compares `colony`, bare `simp_all`, `intros; omega`, and `intros; grind`. Select a smaller run with `--strategies colony --no-build` after a successful build. These are explicit baseline invocations, not tuned competitors. Each row uses a fresh Lean subprocess, and its wall time includes Lake startup and imports. A single run is not a statistically meaningful timing comparison.

To inspect proofs directly:

```sh
cd lean
lake build
lake env lean Pilot.lean
lake env lean SeedProofs.lean
```

| Case | What it checks |
| --- | --- |
| `arithmetic_monotonicity` | An elementary Presburger implication |
| `reverse_accumulator_length` | Recursive reversal preserves total input/accumulator length |
| `count_accumulator_invariant` | A recursive counter equals processed count plus list length |
| `recursive_program_nonvacuity` | Concrete successful executions of both recursive programs |
| `account_state_invariant` | Deposits preserve a balance/received/reserve invariant |
| `allocated_payments_cover_sales` | Separate allocations cover the sum of both prices |
| `allocated_payments_nonvacuity` | A concrete valid allocated payment |
| `shared_payment_attack_witness` | The unsafe rule accepts one insufficient shared payment |
| `false_shared_payment_safety` | A false universal statement must fail; both related positive witnesses must succeed |
| `reverse_involution_frontier` | A true statement beyond the initial portfolio; future certification is progress |

The initial `by colony` tactic introduces binders, tries ordinary proof-producing simplification/arithmetic/decision branches, and tries structural induction with generalized non-proposition locals. This is a minimal deterministic seed with no architecture commitment and no runtime agents. It depends only on Lean's bundled libraries and uses neither an SMT solver nor runtime LLM calls.

`seed-v1.json` is the challenge manifest. `seed-v1.lock.json` binds its full bytes and the toy model source by SHA-256. Any intentional challenge revision requires a reviewable specification change with a new or explicitly updated lock. The evaluator also records all Lean source hashes, its source hash, exact toolchain version, exact statement and generated source hashes, per-case timeouts, exit status, axioms, and diagnostic output. It refuses a run whose sources changed while evaluating.

The JSON schema is `colony.benchmark_run.v1`. `results` contains one row per strategy/case, with `status`, `wall_seconds`, `axioms`, and source digests. `summary[strategy].positive_certified / positive_total` is the seed solved count; negative and unsupported rejections are separate. `certified` means local elaboration plus the standard axiom allowlist, under the pilot's trusted evaluator assumptions. It does not mean independent external replay. See [the proof contract](../docs/proof-contract.md).

The command exits 0 when the Colony positives and negative sanity gate pass and no evidence/process error occurred. Expected baseline proof failures are normal. Timeouts and broken environments cannot masquerade as a correctly rejected negative. Generated reports contain real local measurements; do not fabricate results to populate a dashboard.

For a Linux runner with `bubblewrap` and the pinned release toolchain installed, add this separate replay gate after the evaluator:

```sh
cd lean
lake check --paranoid
```

This command exports the default targets (including all eight positive seed proofs), enforces standard axioms, and invokes the bundled checkers. Its syntax was verified with Lean 4.35.0. The macOS attempt exits 2 because Linux namespaces are required; local benchmark results still explicitly record no independent replay. Challenge/solution comparison in a protected external evaluator remains a separate acceptance milestone.
