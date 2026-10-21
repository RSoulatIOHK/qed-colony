# Roadmap

## North star: the complete pinned Blaster benchmark corpus

The performance target is all 671 canonical harness slots in the 12 upstream
Blaster-benchmarking families, with their original statements and definitions.
See [the north-star contract](blaster-north-star.md) and its locked source
inventory. The initial 12-case NNG4 prefix is a pilot, and 12/12 on that prefix
is not completion of this objective.

Prioritize generic mathematical automation driven by measured corpus failures,
and admission of currently unattempted source-order cases. Extend NNG4 beyond
the first 12, then the other families. Do not fill the research queue with new
state-machine scaffolds as a substitute for coverage. Independent experiments
should own different files or integration surfaces and avoid active objectives.
Workers may prepare admission artifacts within their existing scopes; protected
benchmark/evaluator changes need separate controller governance. Every scored
proof remains exactly `by colony`; source ambiguities, unattempted cases and
invalid controls must stay visible. Architecture remains open.

## Bootstrap: an inspectable local pilot

- Durable dependency-aware task queue, leases, and restart recovery.
- Bounded worker invocation in separate Git worktrees.
- Read-only live Observatory and explicitly timestamped static export.
- Local proof-producing Lean tactic, seed problems, false and unsupported controls.
- Public PR with independent review and reproducible checks.

This milestone demonstrates the development loop, not a superior prover.

## Trust boundary and autonomous integration

- Evaluate a modern pinned Lean port and externally administered `lake comparator` challenge.
- Sandbox build/export and independently replay proof artifacts.
- Run workers in disposable containers or VMs; Git worktrees alone are not process or credential isolation.
- Add narrow GitHub App publication broker, independent review identities, protected policy deployment, and tested gated merges.
- Recover worker/PR/CI state across controller restarts.
- Enforce resource allocations, retry ceilings, and measured daily spending limits outside worker authority.

## Competing research programs

- Run bounded head-to-head experiments in symbolic execution, compositional VC generation, induction, and proof-producing decision procedures.
- Freeze external challenge families and compare against pinned Blaster and other relevant tactics.
- Optimize complete certified latency, memory, and proof size.
- Keep the pilot tactic only if evidence supports it.

## Plutus Gauntlet

- Pin exact compiled scripts and formal semantics.
- Prove preprocessing/translation correctness or avoid uncertified transformations.
- Make fuel/budget/failure distinctions explicit and provide successful witnesses.
- Verify a batch marketplace resistant to multi-satisfaction; publish concrete vulnerable variants.
- Extend to stateful contracts and compositional invariant proofs.

## Generalization

- Prospective third-party challenges after release freeze.
- Larger programs and diverse language frontends.
- Independently reproduced performance and assurance claims.
