# QED Colony

**Built by a swarm. Checked by Lean.**

QED Colony is an autonomous research laboratory building a local, deterministic Lean 4 tactic for program verification. Agents discover benchmarks, propose architectures, implement changes, review one another, and publish their evidence in pull requests. The released tactic does not call an LLM.

The prover architecture is deliberately open. Lean Blaster is a comparison target, not a required design. The long-term target is meaningful properties of compiled Cardano contracts, with an explicit semantic bridge and proofs accepted by Lean's kernel and independent checkers.

## What exists today

This repository starts with a bounded local pilot:

- A SQLite task queue with dependencies, leases, recovery, and an append-only event history.
- The Observatory: a read-only dashboard backed by actual task and experiment records.
- A bounded Codex worker adapter with isolated Git worktrees and no automatic publication or merging.
- A small Lean tactic and seed benchmark. These are infrastructure checks, **not evidence of superiority to Blaster or verification of deployed Cardano scripts**.

## Run the Observatory

Python 3.9+ is sufficient; the control plane has no third-party runtime dependencies.

```sh
python3 -m colony init
python3 -m colony serve --port 7331
```

Open <http://127.0.0.1:7331>. A static published Observatory is a timestamped snapshot. Local mode polls the running control plane. An idle colony is displayed as idle; the page never simulates workers or proof results.

```sh
python3 -m colony status
python3 -m colony export --output observatory/dist/state.json
python3 -m unittest discover -s tests -v
python3 scripts/evaluate_lean.py --output artifacts/benchmark-results.json
```

Lean requires [elan](https://github.com/leanprover/elan) and the toolchain pinned in `lean/lean-toolchain`.

## Run a bounded research worker

With an authenticated [Codex CLI](https://developers.openai.com/codex/noninteractive/):

```sh
python3 -m colony run --once --role researcher --timeout 180
```

The worker uses your configured model and existing account authentication. It claims one eligible task, runs in a dedicated worktree, records its result, then stops. Results enter review; worker success does not mean a merged change or an accepted proof. See [the worker guide](docs/workers.md) for limits and operation.

## Acceptance and transparency

The project requirements live in [the charter](docs/charter.md), [the proof contract](docs/proof-contract.md), and [the evaluation policy](policy/evaluation.json). Proposed changes to specifications or acceptance rules must be reviewed separately from changes evaluated under those rules.

All durable work belongs in public PRs, including useful negative experiments, prompt changes, and architecture decisions. Local task state and raw worker logs are operational data; publish a curated snapshot and reproduction artifacts, not secrets or private model reasoning.

The bootstrap evaluator is not yet an independently administered security boundary. VM isolation, an external evaluator, protected policy deployment, and independently checked compiled-contract examples are explicit milestones in [the roadmap](docs/roadmap.md).

## License

Apache-2.0. Reused upstream material must retain its license and provenance.
