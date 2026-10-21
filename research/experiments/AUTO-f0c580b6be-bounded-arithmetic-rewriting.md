# AUTO-f0c580b6be: bounded rewriting for commutative arithmetic goals

## Scope and outcome

At base revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`, `colony`'s
arithmetic portfolio tried `omega`, `simp_all` with `omega`, and `decide`. The
commutative multiplication target `a * b = b * a` was not closed by that
portfolio. Added two deterministic fallback attempts: one `rw [Nat.mul_comm]`
and one `rw [Nat.add_comm]`. The `rw` step rewrites one occurrence per attempt;
there is no recursive rewrite search or theorem-name dispatch. The rewrite
bound is therefore one rewrite step per candidate attempt (at most two
candidate attempts, in fixed order). The target succeeds on the multiplication
rewrite attempt.

`Colony.Examples.ArithmeticRewriteProbe.nat_mul_comm_regression` keeps its
statement unchanged across tactic runs and is proved with exactly `by colony`.
A nearby false universal claim, `∀ a b : Nat, a * b = b * a + 1`, is guarded by
`fail_if_success ( ... by colony)`; the example compiles, demonstrating the
false claim was not accepted by `colony`.

## Commands and results

- Source revision before changes: `097a4117c7f7038f8d448217d7836a0d95d41bbe`.
- Pinned toolchain: `leanprover/lean4:v4.35.0` (`lean/lean-toolchain`).
- Failed baseline: `cd lean && lake env lean Colony/Examples/ArithmeticRewriteProbe.lean`
  with the initial theorem body `by colony` and no arithmetic rewrite branches.
  Result: exit 1, `colony: the initial proof portfolio could not close this goal`.
- Final build: `cd lean && lake build Colony`. Result: exit 0,
  `Build completed successfully (14 jobs)`; existing linter warnings in other
  example modules were emitted.
- Fresh example check: `cd lean && lake env lean Colony/Examples/ArithmeticRewriteProbe.lean`.
  Result: exit 0. Both the exact positive proof and guarded negative probe
  elaborated.

The first post-edit direct Lean command was run before rebuilding the changed
`Colony.Tactic` module, so it used its prior `.olean` and failed with the same
portfolio error. Rebuilding `Colony` refreshed that module; the final build and
fresh example check above passed. No theorem, assumption, definition, or bound
was changed to obtain the result.

## Assurance and limits

The result is Lean elaborator kernel acceptance of the ordinary proof term on
the pinned local toolchain. This is a small arithmetic rewriting demonstration,
not a benchmark or general completeness claim. No exported replay,
independent-kernel validation, or Cardano execution correspondence was checked.
