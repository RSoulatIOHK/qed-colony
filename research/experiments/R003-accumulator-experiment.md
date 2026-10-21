# R003: bounded accumulator experiment

Author: `frontier-scout`, through the actual bounded Codex worker adapter.

Starting revision: `bd76a8576962c84e5fa7ea7f2c2c662b28f57e33`. Artifact entered review; no code was changed and no measurements are claimed.

R003 proposal: add one deterministic accumulator-normalization branch to `colony`.

**Hypothesis.** A kernel-proved bridge
`∀ (xs acc : List Nat), reverseAcc xs acc = xs.reverse ++ acc`
will let a bounded rewrite branch solve `reverse_involution_frontier` within the existing limits of 15 seconds and 200,000 heartbeats. The permitted files do not expose `reverseAcc`’s defining equations; proving this bridge is part of the experiment.

**Original target.** Preserve exactly:
```lean
∀ (xs : List Nat), reverseAcc (reverseAcc xs []) [] = xs
```
Do not alter definitions, assumptions, benchmark specifications, permitted axioms, or resource bounds.

**Expected proof path.** Prove the bridge by structural induction on `xs`, generalizing `acc`. Simplify with the existing defining equations, the induction hypothesis, and ordinary list reversal and append laws. Rewrite both `reverseAcc` applications in the original target using the bridge, then close with append identity and reverse involution. Every step must construct an ordinary Lean proof term.

**Experiment steps.**

1. Allocate at most two implementation hours, one auxiliary lemma, one deterministic tactic branch, and three candidate proof scripts. Record the exact implementation revision and pinned toolchain.
2. Attempt the bridge proof without modifying protected sources. Add a narrowly scoped rewrite branch using the proved lemma.
3. Under the unchanged benchmark limits, attempt the original frontier and rerun the seed suite, including non-vacuity and intentionally invalid cases.
4. Retain proof-checking evidence, the resulting declaration’s axiom report, resource observations, and any failed attempts with their reasons.

**Exact acceptance criterion.** The unchanged frontier closes through `colony`; Lean’s kernel accepts its proof; its transitive axiom dependencies remain within the manifest’s allowlist; previously solved positive and non-vacuity cases remain solved; and `false_shared_payment_safety` remains unproved. A successful process exit alone is insufficient. Report this assurance as Lean kernel acceptance, without claiming exported replay, independent-kernel acceptance, or Cardano correspondence.

**Stop condition.** Stop at the first exhausted budget, unprovable bridge under unchanged definitions, resource-limit failure, or acceptance regression. Record a negative result without expanding search or weakening the challenge.

This is an unmeasured proposal based only on the four permitted files.
