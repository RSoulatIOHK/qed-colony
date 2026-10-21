# The full Blaster corpus as Colony’s north star

The target is the complete source corpus selected by the pinned upstream latest
runner, with every admitted theorem attempted using exactly `by colony`.
[Blaster-benchmarking at b7cc5304](https://github.com/input-output-hk/Blaster-benchmarking/tree/b7cc5304bde87c269bb3ba57e560304ffd9f2189)
provides 671 canonical harness slots across 12 families. This count follows
`latest/run_latest.sh`, `benchmarks/benchmark_config.sh` and
`benchmarks/benchmark_core.sh`; it is not a claim of 671 distinct mathematical
theorems or of a runnable full-suite comparison today.

| Family | Canonical slots |
|---|---:|
| NNG4 | 108 |
| STG4 | 52 |
| ITL4 | 44 |
| MiniF2F | 96 |
| Verina | 108 |
| UPLCWidth | 6 |
| UPLCDepth | 7 |
| BlasterHome | 50 |
| SmtHome | 50 |
| AutoHome | 50 |
| AesopHome | 50 |
| HammerHome | 50 |
| Total | 671 |

## Source and target integrity

The [inventory](../benchmarks/blaster-full-inventory.json) records the tracked
source tree, Git blobs and SHA-256 hashes, declaration headers and source lines,
imports and dependency pins, upstream selection rules, support-prefix hashes,
and explicit bindings for the existing governed 12-case suite. Its separate
lock pins those inputs. The builder reads source and Git objects; it never runs
upstream Lean, Python, shell or benchmark generators to construct the index.
Static lexical inventory is distinct from Lean elaboration or proof checking.

The 671 slots exclude twelve noncanonical declarations: nine anonymous NNG4
examples with Type-valued targets and three later Verina declarations. They
remain visible in the inventory. The checked-in UPLC depth corpus contains seven
files even though the generator’s current size list has six; the frozen source
index preserves the seventh. Existing Home families retain their source slots;
we do not advertise their sum as distinct mathematics.

Verina cases 47 and 48 are blocked for target review. The upstream harness
selects their first helper theorem and truncates the later intended program
specification. The catalog preserves both identities and flags this mismatch.
Proving the helper cannot establish the intended program property. Correcting
those targets requires a separately reviewed benchmark version; it cannot
silently improve a tactic implementation’s score.

## Honest progress in the Observatory

The 12-case NNG4 prefix is the initially admitted measured suite. The entire
corpus remains the denominator for north-star coverage. Twelve attempted slots
leave 659 unattempted, including the two blocked Verina slots. Awaiting admission
and source-blocked work are separate from proof failures, timeouts and errors.
Scores from saved or superseded revisions are historical and cannot be combined
into a result for current main. Missing or mismatched evidence cannot create
progress. The full inventory never supplies a fallback success count.

Every admitted case must preserve its original statement, definitions,
assumptions and bounds. Its entire proof body is `by colony`, with no target
helper proofs or manual steps. Positive witnesses and invalid cases remain
separate controls. Standard Lean proof terms and actual axiom evidence are
required; local kernel acceptance, exported replay, independent-kernel
acceptance and Cardano execution correspondence remain different assurances.

## Admission work and implementation priorities

First admit the remaining 96 named NNG4 targets in deterministic source-order
shards, retaining unprovable goals and all failed attempts. A collection must
bind every shard to the same tested revision, source catalog and measurement
protocol. Bounded partial work is explicitly partial; it cannot mix revisions
or disappear from the denominator. Each shard needs its own non-vacuity and
invalid controls and the same resources for every compared strategy.

Then admit the other families with their preserved dependency and definition
closures. Mathlib, program specifications and UPLC formalization need explicit
compatibility review. The source corpus uses Lean 4.24, while the current pilot
uses 4.35. Upstream family timeouts also differ, including 90-second UPLC slots.
Neither a source inventory nor a port establishes a matched Blaster score.
Fair comparisons must pin matching challenges, toolchains and resource profiles.

The research planner receives coverage gaps even after the prefix reaches
12/12. It should improve generic mathematical automation and propose admission
work against this corpus, rather than treat newly constructed examples as the
performance target. Workers may propose admission artifacts under their existing
scope. The controller reviews and integrates any protected manifest, evaluator
or resource change in a separate governance PR; an implementation cannot change
its own scoring rules. No tactic architecture is prescribed by this north star.
