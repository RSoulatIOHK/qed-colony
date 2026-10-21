# Bounded workers

Workers use `codex exec` with the existing authenticated CLI. The single-run adapter below inherits the configured model. The persistent supervisor uses adaptive routing: GPT-6 Luna at medium reasoning for an initial attempt, GPT-6 Sol and then GPT-6.1 Sol for bounded revisions, and a stronger reviewer for tactic changes. It records each selection and its reason. No new API key is required.

```sh
python3 -m colony init
python3 -m colony run --once --role researcher --timeout 180
```

Every invocation runs **at most one** eligible task. The worker's dependency-aware claim is leased; heartbeats renew it while the controller is alive. The controller creates a new `codex/` branch and Git worktree from the exact committed HEAD. Uncommitted changes in your checkout are not copied.

Default execution is read-only. The controller checks the requested timeout and sandbox against repository configuration before claiming any task. The defaults permit only `read-only` with a maximum timeout of 180 seconds. The adapter never uses an unrestricted sandbox. It uses the CLI's configured model, records the reported token usage, and applies a wall-time/output cap. Dollar costs remain unknown unless an actual billing source is connected; no inferred spend is displayed as fact.

Implementation workers require an explicit policy change in `colony.json`, reviewed through the project's governance process. For example:

```json
{
  "workers": {
    "max_concurrency": 4,
    "max_timeout_seconds": 300,
    "allowed_sandboxes": ["read-only", "workspace-write"],
    "lease_seconds": 300
  }
}
```

With that policy, an engineering task can run as follows:

```sh
python3 -m colony run --once --role engineer --timeout 300 --sandbox workspace-write
```

The model deadline starts before launching the CLI and includes prompt delivery. Nonblocking POSIX pipes stream input and output in chunks of at most 64 KiB; there is no unbounded reader queue. Local output is limited to 8 MiB in total and 1 MiB per JSON event. The controller reads at most 16,000 characters from the final artifact for the task summary. Oversized logs fail the task; truncating a final summary does not certify its contents. Raw logs stay local and are never copied into the public event stream.

The controller sends SIGTERM to the process group on cancellation, then SIGKILL after a short grace period. It also cleans up remaining children after the CLI leader exits. This does not contain a process that deliberately creates a new session. Setup uses bounded Git calls; the deadline applies to CLI execution rather than Git setup. Task leases are renewed before launching and every 20 seconds during execution. `lease_seconds` must be between 120 seconds and 24 hours. `max_timeout_seconds` must be between 1 and 3600 seconds; each invocation's `--timeout` must stay within that limit.

The single-run adapter permits four concurrent workers by default through a SQLite reservation. The persistent supervisor defaults to one active worker and a shared daily budget, bounded revisions, public PRs, independent model review, required CI, and exact-head merging. The reservation is extended after setup to cover the model deadline and cleanup. A successful worker result enters `review`, not `done`. The controller retains the worktree and raw logs beneath ignored `.colony/` for inspection. The final research result is part of the task summary; check it before publishing a snapshot.

The worker is instructed not to push, contact others, deploy, change policy, or expand its authority. GitHub environment tokens are removed from its inherited environment. These are useful pilot restrictions, **not a complete credential or process security boundary**: the existing user account, keychain, global CLI configuration, or plugins may expose capabilities. Production workers must run in disposable containers or VMs with scoped credentials and an independent publication broker.

The read-only Observatory does not start workers. The persistent service drives execution and reports its heartbeat independently of the web server. On restart it verifies recorded process identities before stopping surviving CLI groups, marks interrupted attempts uncertain, and retains their budget reservation. This recovery cannot contain intentionally detached malicious processes; disposable execution environments and independently owned acceptance administration remain production milestones. See [autonomy](autonomy.md) and [the publication pipeline](pipeline.md).

Official interface reference: [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive/).
