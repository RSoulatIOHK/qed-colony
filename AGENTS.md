# Working in QED Colony

The human owner does not write implementation code. Agents should carry scoped work to a reviewable result and record evidence.

## Product requirements

- The released Lean tactic runs locally and deterministically, without an online LLM.
- No architecture is mandatory. Lean Blaster is a baseline, not a design constraint.
- A successful proof must establish the original specified theorem. Preserve theorem statements, definitions, assumptions, and bounds in scored comparisons.
- Never use `sorry`, `admit`, arbitrary axioms, native evaluation axioms, or disabled kernel checks to claim a certified result.
- Label the exact assurance achieved. Elaborator kernel acceptance, exported replay, independent-kernel acceptance, and correspondence to Cardano execution are distinct claims.
- Benchmarks must include non-vacuity and intentionally invalid cases where relevant.

## Workflow

- Scope a task and acceptance criteria before implementation. Record failed experiments and why they failed.
- Use a `codex/` branch and public PR for every durable change.
- A worker must not push, open a PR, merge, contact other people, deploy, change credentials, or increase its own authority. The controller performs authorized publication after reviewing artifacts.
- Implementation workers may propose changes to policy, challenge statements, or measurement, but those require a separate governance PR and cannot improve that implementation's score.
- Run checks appropriate to the change. Keep the pilot dependency-light.
- Never put credentials, machine-specific paths, private logs, or fabricated activity in tracked files or the Observatory.
- Use actual source revisions, command results, and artifacts. A process exit code is not a proof certificate.

## Initial checks

```sh
python3 -m unittest discover -s tests -v
node --check observatory/dist/app.js
python3 scripts/evaluate_lean.py --output artifacts/benchmark-results.json
```

The initial Python evaluator is a local pilot, not a tamper-proof security boundary. The roadmap calls for externally owned challenge/configuration, sandboxed export, `lake comparator`, and independent kernels on a modern pinned Lean toolchain.
