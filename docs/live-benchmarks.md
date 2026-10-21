# The live benchmark report

The Observatory's Live benchmark view reports deterministic checks of a frozen
external challenge against the colony tactic and fixed automation baselines.
The runner follows reviewed public `origin/main`; it never scores an unfinished
worker checkout. It uses no LLM and consumes no colony model attempt.

## Proof contract

Every scored Colony declaration has exactly the proof body `by colony`.
There are no surrounding `cases`, `induction`, simplification steps, alternate
proofs or handwritten helper lemmas. The tactic itself may use ordinary Lean
proof procedures internally: the requirement is that one invocation closes the
unchanged challenge. Manual proofs in research examples do not become benchmark
successes.

The pinned extractor preserves each original declaration header, binders,
assumptions and namespace context. It removes the upstream placeholder proof.
The original vendored file is provenance data and is never imported into a test.
Each challenge imports only `Colony.Tactic`, rather than the library's examples
and their manually proved helper facts. Each tactic receives the same challenge,
toolchain, heartbeat limit and per-case timeout in a fresh Lean process.

The initial restricted candidate profile rejects explicit local mathematical
proof declarations and proof-valued helper definitions in the tactic's import
closure, including helpers hidden under other namespaces. Compiler-generated
constructor and deriving facts remain allowed. More general certified algorithms
may need a separately reviewed profile; a rejected profile is an error, not a
proof failure or a lower-scoring theorem.

The strategy bodies are fixed in the reviewed evaluator, not supplied by a
worker or free-form manifest field. The report exposes the generated Lean source
and statement hash for every row. Kernel acceptance also requires the expected
axiom report and rejects nonstandard axioms, including admissions and native
evaluation axioms. A successful process exit alone cannot count as a proof.
Failures, timeouts and infrastructure errors remain visible. Invalid claims and
positive witnesses are separate controls and never inflate the theorem count.

## Initial upstream sample

The first suite is the first 12 named theorems, in source order, from
[NNG4.lean](https://github.com/input-output-hk/Blaster-benchmarking/blob/b7cc5304bde87c269bb3ba57e560304ffd9f2189/BlasterBenchmarks/NNG4/NNG4.lean).
The complete original source, Apache-2.0 license, immutable commit, Git blob and
SHA-256 hashes are retained. Selection was fixed before measuring proof success.
The remaining 96 named theorems and nine unnamed examples are not scored.

This is a Lean 4.35 rehost of statements from an upstream Lean 4.24 benchmark.
The local baselines share the same Lean 4.35 environment. A runnable, matched
Blaster comparison is not available; the report must not show an invented
Blaster score or claim superiority over it.

## Refresh and installation

After the governance PR is reviewed and merged, install the independent runner
from the reviewed checkout:

```sh
python3 -m colony benchmark-service install --interval 120
python3 -m colony benchmark-service status
```

`start`, `stop` and `uninstall` are also supported. Installation copies the
evaluator, frozen corpus and their validation code into an ignored pinned
runtime. Candidate source checkouts cannot replace that configuration. The
background runner has a single-run lock, bounded processes and atomic report
publication. A failed or incomplete run keeps the previous complete report and
explicitly marks it stale. The displayed tested revision, target revision and
timestamps distinguish a completed result from work in progress. Freshness is
relative to the runner's last observed public main revision; polling is not a
claim of instantaneous remote synchronization.

The research planner receives bounded, revision-bound failure diagnostics from
valid reports. It can propose generic solver improvements, while the corpus and
measurement rules remain protected governance inputs.

Timing includes process startup and imports on a shared development machine.
It is diagnostic timing, not a statistically established performance ranking.
Assurance is Lean elaborator/kernel acceptance with a standard axiom allowlist;
exported replay and independent-kernel acceptance are separate checks.

These controls resist accidental score manipulation within the local workflow.
The machine owner can still alter files or the compiler. The independently owned
sandboxed evaluator described by I001 remains a distinct unfinished requirement.
