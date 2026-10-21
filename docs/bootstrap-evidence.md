# Bootstrap evidence

The first implementation was produced by three parallel agents: control plane, Observatory, and Lean proof/benchmark development. The root coordinator integrated their output and implemented the bounded worker adapter, project policy, and publication workflow.

## Measured proof pilot

The checked-in report at `benchmarks/results/bootstrap-lean435.json` contains actual output from forty fresh Lean processes on the pinned Lean 4.35.0 toolchain. Eight positive seed properties certify with the initial `colony` tactic. The deliberately false shared-payment claim is rejected, with separate proofs of an attack witness and a valid allocation. The true reverse-involution frontier remains unsolved.

Bare `simp_all`, `intros; omega`, and `intros; grind` are recorded as development controls. They are untuned single invocations on a hand-picked seed suite. These results establish neither superiority to Lean Blaster nor broad superiority to other Lean tactics.

The report records source and statement hashes, exact toolchain, standard axioms, wall time, failure categories, and scope. Its assurance is ordinary local Lean kernel elaboration. Independent exported replay is a separate CI check; record that check's actual result before claiming it.

## Independent review

The control-plane agent independently reviewed the coordinator's worker adapter. It identified blocking stdin delivery before the timeout, surviving descendant processes, unbounded output allocation, and unenforced configuration limits. Those findings were accepted for correction with regression cases before the worker pilot.

Browser QA found clipped graph cards and stale ordering of recent signals. The Observatory agent repaired layout bounds and ordering. The dashboard uses actual task/event records and explicitly distinguishes local live data from a hosted timestamped snapshot.

## Actual bounded research runs

The first live CLI worker, R001, reached its 180-second limit and was terminated. Its task remains failed. A separately scoped R003 task produced a concise unmeasured experiment proposal within the same cap and entered independent review. The reviewer requested accurate classification as library-adapter work, equal baseline access to new lemmas, and exact-declaration proof replay. The original proposal and review are retained under `research/experiments/`; no engine improvement is claimed from this proposal.

## Proof replay scope

The first Linux `lake check --paranoid` attempt exported the entire imported environment: 164,067 declarations. The hardened Lean kernel and `lean4lean` accepted it. The run did not complete every checker and was stopped; it is not an overall passing paranoid result. The run is [publicly inspectable](https://github.com/RSoulatIOHK/qed-colony/actions/runs/39567617371).

The revised CI uses comparator's named-root export, checking the eight seed theorems and their transitive dependencies against a separate challenge module. It retains the standard axiom policy and runs Lean's kernel plus `lean4lean`. The checked-in challenge still belongs to this repository; independently administered challenge ownership remains future work.

## Reproduction

```sh
python3 -m unittest discover -s tests -v
node --check observatory/dist/app.js
python3 scripts/evaluate_lean.py --output artifacts/benchmark-results.json
python3 scripts/import_benchmark.py artifacts/benchmark-results.json
python3 -m colony export --output observatory/dist/state.json
```

On Linux with the pinned toolchain and `bubblewrap`:

```sh
cd lean
lake check --paranoid
```

That whole-environment command is an optional, expensive audit. The routine Linux gate is:

```sh
cd lean
lake comparator --config comparator.json
```

The macOS attempt preserves the sandbox and exits with an unsupported-environment diagnostic because Linux namespaces are unavailable. That attempt supplies no independent proof-checking evidence.
