# E001: bounded Boolean case splitting

Scope and acceptance: add one-parameter Boolean splitting after arithmetic and before induction, close every branch with the existing portfolio, restore the candidate state on failure, and validate positive, arithmetic, and invalid examples without changing protected files.

Implemented a deterministic fallback in `Colony.Tactic`: after the existing arithmetic portfolio fails, it tries each local `Bool` parameter in context order. Each candidate splits into false and true and runs the existing omega, simp-plus-omega, or decide portfolio on every branch. Candidate state is restored if any branch stays open. A successful candidate returns from the outer tactic before induction. The bound is one Boolean parameter per attempt; there is no recursive Boolean splitting.

The imported example module checks a natural-valued conditional, a second conditional where the first Boolean candidate fails before the next succeeds, ordinary arithmetic, and an invalid conditional equality guarded by `fail_if_success`. Successful proofs are ordinary elaborated Lean terms.

Failed experiment: the first version returned only from a nested `withMainContext` block. `cd lean && lake build` failed with `No goals to be solved` at the positive example because execution continued into induction. Returning from the outer tactic fixed this.

Checks after the fix: `cd lean && lake build` completed successfully (8 jobs), including `Colony.Examples.BooleanBranching` and `Colony`; `git diff --check` passed. `git diff --name-only 28dcb060b633ca7ce89d676c51f888942c5ad187` listed only `lean/Colony.lean`, `lean/Colony/Tactic.lean`, `lean/Colony/Examples/BooleanBranching.lean`, and this note. The seed statements, comparator, evaluator, toolchain, and CI were unchanged.

This establishes elaborator kernel acceptance of these examples. It does not establish benchmark superiority, exported replay, independent-kernel acceptance, or correspondence to Cardano execution.
