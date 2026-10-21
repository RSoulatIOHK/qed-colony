# AUTO-bbb430c7dd: bounded product splitting

## Scope and source identity

Base revision: `3b11188d52ad5ff8c1f1885508b44c1d6e584f66`.
Tested candidate revision: `64fe3165d234f78daf1d6896b3d08c571f69e1cd`.
The checked source files at that revision have SHA-256 hashes
`a4cc9ce2e59cbac2b7c05fef6171728863f6014f3744bdefe1bedf3cb2a149f8`
(`lean/Colony/Tactic.lean`),
`c081e9c3e7d4c2a0100cb2554d8978bebf64e14b1fe47abe9cabac4bb958a906`
(`lean/Colony/Examples/ProductStateTransition.lean`), and
`5ebba780463f0bbc00e67b77eee9a3640e8ce7c5818707afe1c0695d1f9d75c9`
(`lean/Colony.lean`). This record was corrected after that source revision;
the tested Lean sources were not changed.
The experiment changes only `lean/Colony/Tactic.lean`,
`lean/Colony.lean`, `lean/Colony/Examples/ProductStateTransition.lean`, and
this record. The pinned toolchain is Lean 4.35.0 (toolchain file in `lean/`).

The tactic now scans local declarations in local-context order for product
types, tries one candidate at a time, splits it, and runs `simp_all <;> omega`
on every branch. Each attempt saves its tactic state and restores it if any
branch fails. It does not recursively invoke `colony` from branches. The new
example defines a pair transition which increments both counters, then proves
the unchanged subtraction-difference invariant with exactly `by colony`.
A nearby impossible equality is guarded with `fail_if_success`.

## Experiment outcomes

- `cd lean && lake env lean Colony/Examples/ProductStateTransition.lean`
  initially failed before building dependencies with `unknown module prefix
  'Colony'`; running the package build first resolved the missing `.olean`
  search path.
- The first proposed transition added each counter by a different amount.
  Its difference invariant was false (for example, inputs `0` and `1`), and
  the theorem failed. That candidate was discarded. A common increment was
  chosen instead, preserving the original valid invariant statement.
- `cd lean && lake build` on the tested candidate exited 0: all 16 jobs
  completed, including the new example and aggregate `Colony` module. Existing
  linter warnings remain, including an unused-variable warning in the new
  example.
- `cd lean && lake env lean Colony/Examples/ProductStateTransition.lean`
  exited 0. This elaborates both the positive theorem and the `fail_if_success`
  false-target guard.
- From `lean/`,
  `printf 'import Colony.Examples.ProductStateTransition\n#print axioms Colony.Examples.advancePair_preserves_difference\n' | lake env lean --stdin`.
  It exited 0 and reported `[propext]` as the theorem's axiom dependency.
- `lean --version` reported Lean 4.35.0, commit
  `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`, arm64 Apple Darwin 24.6.0.

## Assurance and limits

The positive theorem was accepted by the Lean elaborator and kernel in the
pinned toolchain; the printed dependency is Lean's standard `propext` axiom.
The `fail_if_success` guard is an elaboration-time check that the attempted
proof of the false equality fails. It does not kernel-check a proof of that
false target.
This is not an exported replay, independent-kernel, Cardano correspondence, or
performance result. The product fallback is bounded to one product-valued
local candidate per attempt, with deterministic candidate order and full
rollback on an unsolved branch.
