# AUTO-f0c580b6be: bounded rewriting for commutative arithmetic goals

## Scope and acceptance

Re-run the active experiment without changing its theorem, assumptions, or proof
body. Require the original theorem to close with exactly `by colony`, record the
rewrite search bound, reject a nearby invalid statement, and check the ordinary
proof term on the pinned Lean toolchain. No benchmark-specific helper or
new theorem-name dispatch is used by this experiment. All changes are confined
to `lean/Colony/Tactic.lean`, its existing example, and `research/`.

## Source and result

- Requested baseline: `097a4117c7f7038f8d448217d7836a0d95d41bbe`.
- Checkout before this run: `705c481d01afb2be1c2b65689851cc3a28c89cdd`.
  This checkout already contained the two rewrite branches and original probe.
  This run documents the bound and adds non-vacuity, counterexample, axiom, and
  reproducible baseline/direct-rejection evidence; it does not claim to have
  newly introduced those existing branches.
- Pin: `leanprover/lean4:v4.35.0`; observed compiler version `4.35.0`,
  compiler commit `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`.
- Final tactic SHA-256:
  `70ac2c6396593584b7ae0b583130a1079caf3a40d4a871dd8763475a0102772f`.
- Final example SHA-256:
  `ce5be3e704f5d4d2570eaf5f940b3c4d5b617c3d348bfa25ed227658e3133f29`.

The unchanged declaration is `Colony.Examples.nat_mul_comm_regression`:

```lean
theorem nat_mul_comm_regression (a b : Nat) : a * b = b * a := by colony
```

It closes. `#print axioms` reports that this declaration does not depend on any
axioms. Neither witness below is used to prove the target: the scored theorem
precedes them, and the tactic does not import the example module.

The example retains its `fail_if_success` check for
`∀ a b : Nat, a * b = b * a + 1`. That guarded attempt fails as required.
A separate direct Lean invocation of the invalid claim exits 1 with
`colony: the initial proof portfolio could not close this goal`, rather than an
import or syntax error. The example also proves the negation of this exact
universal statement by instantiating `a = b = 0`. A nonzero instance of the
positive theorem, `2 * 3 = 3 * 2`, closes with `by colony`. The non-vacuity and
refutation proofs report only `[propext, Quot.sound]` in their axiom dependencies.

## Bound and mechanism

In each call to `arithmeticPortfolio`, `first` tries, in order: `omega`,
`simp_all` followed by `omega`, `rw [Nat.mul_comm]`, `rw [Nat.add_comm]`, and
`decide`. Each candidate is guarded by `solve`, which requires complete closure;
a failed candidate is rolled back before the next candidate. Each rewrite
candidate contains exactly one `rw` application, including its automatic
reflexivity check. There are at most two rewrite candidates per arithmetic
portfolio call, in fixed multiplication/addition order; no recursive rewrite
search, saturation, or theorem-specific helper is introduced. The target closes
on the multiplication candidate (the left product rewrites to the right product).
The bound counts rewrite applications, not the number of expression occurrences
matched internally by `rw`.

This is a bound on the rewriting experiment, not a new global limit on the
existing tactic. Existing Boolean/Option fallbacks can call the arithmetic
portfolio on their own branches, and existing induction remains available after
the portfolio fails. No heartbeat setting, benchmark timeout, or challenge bound
was changed. The replay driver applies a 60-second subprocess timeout as an
execution guard, not as a proof certificate or performance measurement.

## Exact commands and evidence

Run from the repository root unless the working directory is given explicitly.

| Command | Result |
| --- | --- |
| `lake env lean --version` (cwd `lean`) | exit 0; pinned compiler above |
| `lake build Colony` (cwd `lean`) | exit 0; `Build completed successfully (14 jobs)`; existing linter warnings in other examples |
| `lake env lean Colony/Examples/ArithmeticRewriteProbe.lean` (cwd `lean`) | exit 0; exact target, guarded negative, nonzero witness, and counterexample proof elaborate; axiom output above |
| `python3 research/experiments/AUTO-f0c580b6be-check.py` | exit 0; all three expected outcomes below reproduced |
| `python3 -m unittest discover -s tests -v` | 335 tests; FAILED (failures=3, errors=13) |
| `node --check observatory/dist/app.js` | exit 0 |
| `python3 scripts/evaluate_lean.py --no-build --output research/experiments/AUTO-f0c580b6be-evaluator.json` | exit 1; Colony accepts 7/8 positives, 1 timeout, negative sanity passes, 0 evidence errors |

The replay driver and [JSON evidence](AUTO-f0c580b6be-checks.json) record exact
argument vectors, cwd, complete generated standard input, return codes, output,
source revision, and SHA-256 hashes. The driver requires a built `Colony.Tactic`
and `Colony.Procedures.ListState`; run the build command first.

1. Baseline: obtain `lean/Colony/Tactic.lean` using
   `git show 097a4117c7f7038f8d448217d7836a0d95d41bbe:lean/Colony/Tactic.lean`,
   append the unchanged declaration in namespace `Colony.Examples`, then pass
   that complete source to `lake env lean --stdin` (cwd `lean`). This bypasses
   any current tactic `.olean`. Result: exit 1, line 210, portfolio failure.
   Input SHA-256: `4d8a1c8106246d0263e7a38cd9da2d797608270eb876fbbdda6eab1fa33d33b9`.
2. Final positive/guard: direct example command above, exit 0, no axioms for
   `Colony.Examples.nat_mul_comm_regression`.
3. Invalid direct: `lake env lean --stdin` (cwd `lean`), with exactly:

   ```lean
   import Colony.Tactic
   theorem invalid_shifted_mul : ∀ a b : Nat, a * b = b * a + 1 := by colony
   ```

   Result: exit 1, line 2, portfolio failure. No invalid proof is certified.

## Failed attempts and limitations

The baseline portfolio cannot close this target: it has no multiplication
commutativity rewrite, and its existing arithmetic/induction attempts end in the
portfolio failure above. The direct invalid attempt also fails; its failure is
expected and accompanied by a kernel-accepted refutation.

The prior research record described an initial failure caused by checking against
a stale tactic `.olean` before rebuilding. That historical command was not
repeated here and has no retained raw evidence; this run builds the current
module before its final checks. Prior review reported a 480-second worker timeout;
that is not proof evidence. The baseline in this run uses source through stdin
to avoid confusing cached current tactics with the requested baseline.

The existing seed evaluator was run after the successful build with `--no-build`;
its output was directed to an allowed research path rather than `artifacts/`.
The [evaluator evidence](AUTO-f0c580b6be-evaluator.json) records all four configured
strategies with their unchanged challenge statements and bounds. Colony reports
7/8 positives accepted, the `count_accumulator_invariant` case timed out under
the existing 15-second subprocess limit, the negative sanity check passed, one
unsupported frontier was accepted, and there were no evidence errors. Thus the
seed run exits 1 and is not an all-suite pass. This suite does not score the
arithmetic rewrite target; that target is checked separately above. No timing
comparison or diagnosis of the accumulator timeout is claimed.

The Python suite is not green. Its 13 errors report sandbox-denied process
inspection (`ps`) or local socket binding. Its three failures are the missing
process record in `test_unverifiable_cleanup_keeps_process_record_and_worker_slot`,
empty helper-audit output in
`test_compiler_audit_rejects_term_style_proof_def_in_different_namespace`, and
`needs_review` instead of `waiting_network` in
`test_actual_triage_outage_reconnects_after_restart_and_replays_completed_handoff`.
Their causes were not repaired or fully diagnosed in this Lean-only task.
Raw machine-specific tracebacks are not copied into research evidence.

Assurance is local Lean elaborator kernel acceptance of ordinary proof terms,
with the axiom dependencies explicitly reported. No exported replay,
independent-kernel acceptance, correspondence to Cardano execution, general
arithmetic completeness, or performance improvement is claimed. The replay
script is a local evidence aid, not an adversarial security boundary. No commit,
push, PR, or publication was performed; controller integration remains separate.
