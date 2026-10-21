# QED Colony

**Built by a swarm. Checked by Lean.**

[Open the public Observatory](https://qed-colony-observatory.iohk-9108.chatgpt.site/) · [GitHub Kanban board](https://github.com/users/RSoulatIOHK/projects/15) · [Browse pull requests](https://github.com/RSoulatIOHK/qed-colony/pulls)

The public Observatory shows timestamped colony snapshots. Its Kanban view groups recorded work and exposes review, CI, budget, and intervention blockers. The local Observatory shows live controller activity while its service is running. The [GitHub Project](https://github.com/users/RSoulatIOHK/projects/15) tracks public issues and PRs; a separate local sync job updates it every two minutes. See [board setup](docs/github-project.md).

QED Colony is an autonomous research laboratory building a local, deterministic Lean 4 tactic for program verification. Agents discover benchmarks, propose architectures, implement changes, review one another, and publish their evidence in pull requests. The released tactic does not call an LLM.

The prover architecture is deliberately open. Lean Blaster is a comparison target, not a required design. The long-term target is meaningful properties of compiled Cardano contracts, with an explicit semantic bridge and proofs accepted by Lean's kernel and independent checkers.

## What exists today

This repository includes a bounded, persistent local colony:

- A SQLite task queue with dependencies, leases, recovery, and an append-only event history.
- The Observatory: a read-only dashboard backed by actual task and experiment records.
- A restartable controller that takes scoped tasks through implementation, public PRs, independent agent review, CI, and head-pinned merging.
- Adaptive model routing: GPT-6 Luna at medium reasoning first, stronger Sol models on retries and proof-sensitive review. All attempts share a daily runtime budget.
- A pinned macOS user service that survives the chat closing. The Mac must remain awake and connected for work to progress.
- SRE workers for scoped controller fixes and an operations steward that audits bottlenecks and proposes missing roles and reviewed follow-up jobs. See [roles and handoffs](docs/roles.md).
- A small Lean tactic and seed benchmark. These are infrastructure checks, **not evidence of superiority to Blaster or verification of deployed Cardano scripts**.

## Run the Observatory

Python 3.9+ is sufficient; the control plane has no third-party runtime dependencies.

```sh
python3 -m colony init
python3 -m colony serve --port 7331
```

Open <http://127.0.0.1:7331>. A static published Observatory is a timestamped snapshot. Local mode polls the running control plane. An idle colony is displayed as idle; the page never simulates workers or proof results.

## Run the unattended colony

With authenticated Codex and GitHub CLIs, install the persistent macOS service:

```sh
python3 -m colony init
python3 -m colony service install --port 7331
python3 -m colony service status
```

The current experimental policy permits up to four independent model workers in parallel, sharing 28,800 aggregate model seconds (eight worker-hours) and 216 attempts per Paris calendar day. Each cycle has its own worktree; publication, review handoffs, CI polling and merges remain serialized controller operations. It reserves each call's full timeout before starting, records actual runtime and usage, and resumes after the daily reset. Runtime is an enforceable scheduling unit, not a dollar or subscription-credit estimate. Interrupted calls retain their full reservation.

Only scoped tactic/example/research changes can be published and merged automatically. Benchmark definitions, CI, the controller, and its policy require a separate governance change. A merged repository change does not replace the deployed controller: service installation pins its code and configuration. See [autonomy](docs/autonomy.md), [the pipeline](docs/pipeline.md), and [service operation](docs/service.md).

```sh
python3 -m colony service stop
python3 -m colony service start
```

For a foreground controller on a supported POSIX system, use `python3 -m colony supervise --port 7331`. The service's dashboard occupies this port while it is running.

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
