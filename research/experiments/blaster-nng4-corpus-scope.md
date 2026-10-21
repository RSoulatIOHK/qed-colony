# Frozen Blaster NNG4 pilot corpus

Scope: preserve the first 12 named theorem declarations, in source order, from
`input-output-hk/Blaster-benchmarking` revision
`b7cc5304bde87c269bb3ba57e560304ffd9f2189`, file
`BlasterBenchmarks/NNG4/NNG4.lean`. This is a small deterministic prefix, not the
full upstream benchmark or a claim about Blaster performance.

Acceptance: retain and hash the exact upstream source and Apache-2.0 license;
reconstruct each declaration's original namespace, section, abbreviation and
open commands; remove its upstream proof and every other target declaration;
freeze extraction, selection, toolchain and resource limits; reject changed
inputs or reordered/substituted targets. Only `Colony.Tactic` may be imported.
Every scored candidate proof must be exactly `by colony`; no surrounding proof
steps, extra helper declarations or imports are permitted.

Upstream pins Lean 4.24.0. The pilot rehosts the same statements on the colony's
Lean 4.35.0, with a 20-second deadline and 200,000 heartbeats per declaration.
Report that version difference and all failed or unattempted targets. No official
cross-toolchain score, solver-superiority claim, or independent-kernel replay is
established by this extraction.

The source contains placeholder proofs. They are retained only as vendored
provenance data and are never imported into a checking process. The extractor
must fail closed on unsupported surrounding commands or declaration syntax.

## Extraction evidence

The source inventory contains 108 named theorems and nine unnamed examples.
This version selects exactly the first 12 named theorems; 96 named theorems and
all nine unnamed examples remain outside its score. The selected prefix includes
addition identities and cancellation followed by multiplication monotonicity.

Pinned source and license were retrieved through the GitHub connector. Their
exact bytes were verified against both upstream Git blob identities and SHA-256
hashes recorded in the manifest. `python3 scripts/extract_blaster_nng4.py --write`
and subsequent validation passed. The ten corpus tests passed; they exercise
changed statements, reordered goals, injected context/helpers/imports, altered
limits, changed source/license bytes, and symlink substitution. These attacks
were rejected in isolated test directories. `git diff --check` passed.

Freezing the corpus did not run `colony` or establish a proof result. The live
runner must produce the revision-bound proof and failure evidence separately.
