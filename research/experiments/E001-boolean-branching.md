# E001: bounded Boolean case splitting

Implemented a deterministic fallback in `Colony.Tactic`: after the existing arithmetic portfolio fails, it tries each local `Bool` hypothesis in context order. Each candidate splits into false and true and runs the existing omega, simp-plus-omega, or decide portfolio on every branch. Candidate state is restored if any branch stays open; structural induction remains after this fallback.

The example module contains a conditional disjunction, an ordinary arithmetic regression, and an invalid goal guarded by `fail_if_success colony`. Successful proofs are ordinary elaborated Lean terms. No theorem seed, comparator, evaluator, toolchain, or CI file was changed.

Check: `cd lean && lake build` failed while compiling the Boolean positive example with `No goals to be solved` at its `colony` invocation. The ordinary arithmetic regression and invalid-goal check have not yet been validated in a complete build. No benchmark superiority, independent-kernel replay, or correspondence to Cardano execution is claimed.
