# Proof contract

The released tactic must run locally and reproducibly without an LLM. Agents develop the implementation; they are not part of tactic execution. The prover architecture remains open. The initial `colony` portfolio is disposable scaffolding for testing the engineering and verification loop.

## What this pilot establishes

`lean/` pins the Lean 4.35.0 toolchain and depends only on its bundled libraries. Successful seed proofs elaborate to ordinary Lean terms, with reachable axioms printed for each benchmark declaration. The evaluator accepts only the standard Lean foundations `propext`, `Quot.sound`, and `Classical.choice`; it rejects `sorryAx`, arbitrary additional axioms, and native reduction axioms. It requires the expected declaration's axiom evidence and a successful process exit, not merely an exit code of zero.

The trust label is **Lean elaboration kernel; standard axiom allowlist; no independent external replay**. This describes the local evidence collected; it is not a security guarantee for arbitrary agent-written Lean metaprograms. A metaprogram can print misleading output or execute code. The Python evaluator and its stdout parser are not an adversarial verification boundary. Neither is a `#print axioms` command alone.

The project builds and all eight seed positives certify on Lean 4.35.0, a modern pin including the [kernel fixes released in Lean 4.33.0](https://lean-lang.org/doc/reference/latest/releases/v4.33.0/). A compiler pin does not turn this local pilot into an independent replay or a production security audit.

## Challenge and solution separation

The challenge consists of the exact theorem statements in `benchmarks/seed-v1.json` and the definitions in `lean/Colony/Seeds.lean`. The adjacent challenge lock records their SHA-256 digests. The evaluator rejects mismatched digests and records all Lean sources, its own source, Lake configuration, toolchain version, generated challenge source, statements, and manifest digests. Sources must remain stable throughout a run.

The lock catches accidental drift. It does not stop a contributor from editing both a specification and its lock. Public PR review and ownership of protected challenge files remain necessary. An implementation improvement should preserve the protected challenge. Specification changes require a separate, explicitly reviewed comparison; make any weakening visible. Versioned benchmark changes must retain previous results and explain changes in semantics.

Each challenge runs in a fresh Lean process with a wall timeout and a heartbeat budget. Positive certification, ordinary tactic failure, timeouts, process errors, missing evidence, and extra axioms are distinct statuses. False statements count as correctly rejected only after ordinary proof failure and successful positive proofs of a concrete attack witness and a valid allocated-payment transaction. A timeout or broken import cannot satisfy a negative check. Rejections never count toward the positive solved score.

## Next acceptance boundary

Before evaluating untrusted agents as proof producers, establish independently owned challenge validation on the pinned modern toolchain. [Lean 4.35.0](https://lean-lang.org/doc/reference/latest/releases/v4.35.0/) adds `lake check` and `lake comparator`, including a paranoid mode with independent checkers. The [official validation guidance](https://lean-lang.org/doc/reference/latest/ValidatingProofs/) recommends a trusted challenge and a separately judged proposed proof.

The future runner must keep the challenge outside the solution's write authority, sandbox elaboration, export the proof data, compare the exact challenge and solution declarations, and replay the exports through the selected kernels. Record checker identities, versions, results, challenge/solution hashes, axiom policies, resources, and all rejections. A successful toolchain port or a `lake build` must not be mislabeled as having completed this independent replay. Test the acceptance boundary with deliberately malicious solutions before granting automatic merge authority.

The seed replay gate now uses `cd lean && lake comparator --config comparator.json` on Linux with `bubblewrap`. Its separate `Challenge.lean` module states exactly the eight original positive manifest goals, checked by a source/manifest mapping test. The challenge uses ordinary bundled tactics to fill its own proofs and does not call `colony`; comparator compares the prescribed types and definition closure with the `SeedProofs` solution. No proof holes are required.

The configuration selects `lean4lean --import` in addition to the default Lean kernel. Comparator exports the named roots, their full transitive proof dependencies, allowed axioms, and required primitives. This avoids exporting unrelated tactic implementation constants while retaining every dependency needed to check the claimed proofs. Challenge and configuration require protected review. They remain in the same repository as the solution, so separately controlled challenge ownership is still a governance milestone.

An optional `lake check --paranoid` audit covers the broader default-target environment and all bundled checkers; it is not required for the bounded seed replay gate. The [Lake documentation](https://lean-lang.org/doc/reference/latest/Build-Tools-and-Distribution/Lake/) describes both commands. Local command/help validation and named-root export succeeded on Lean 4.35.0. A sandboxed command attempt on macOS returned exit code 2 because `bwrap` needs Linux namespaces; no checker ran and the sandbox was not disabled. Record actual Linux CI acceptance and exact checker scope separately; do not infer it from the local evaluator report.

The full path must be certified: original statement, preprocessing, solver inference, reconstructed proof, and final theorem. Runtime native evaluation, external solver success, or an unchecked normalization is insufficient for the intended trust track.

## Program and Cardano claims

The current suite verifies tiny list, account, and payment models written directly in Lean. It has no ledger model, transaction encoding, execution cost semantics, UPLC interpreter, compiled Plutus artifact, or proof of correspondence to Cardano. `allocatedSales` is a four-natural-number allocation predicate. Its unsafe variant intentionally reuses one payment. These are unit cases that exercise the pipeline, not smart-contract proofs.

A future Cardano challenge must identify the exact source and compiled script, compiler settings, ledger and UPLC versions, serialization, assumptions, and any execution/resource bounds. A forked formalization needs independently reviewed semantic correspondence and conformance evidence. State nonvacuity and attack witnesses alongside safety properties. Preserve original challenge meaning when optimizing representations, proving a bridge when necessary.

No current result establishes superiority to Lean Blaster. Such a claim needs matched tasks, pinned baselines and toolchains, comparable trust tracks, reproducible resource budgets, balanced problem families, and complete accounting for preprocessing, proof reconstruction, and kernel checking. The initial tactic's success on eight hand-picked seed positives is development progress only.
