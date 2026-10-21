# AUTO-abd0a5c138: bounded monotonicity chaining for ordered products

## Scope and acceptance

Probe whether `colony` can compose applicable local monotonicity facts for an
ordered product. The example lives in its own file; its positive theorem is
closed with exactly `by colony`. A reversed-direction hypothesis must not
close the reversed conclusion. The search is deterministic and bounded.

The checkout at base revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`
contained no ordered-product theorem or prior experiment to preserve. The
example therefore defines `orderedProduct` as right-folded natural
multiplication and tests the chain theorem stated in
`lean/Colony/Examples/OrderedProduct.lean`.

## Change

Added two generic `le_trans`/`assumption` attempts to the start of the
arithmetic portfolio in `lean/Colony/Tactic.lean`. Each attempt can descend at
most two transitivity applications per branch, so a single proof path can
compose at most three inequalities. There is no ordered-product identifier,
theorem-name dispatch, loop, or generated helper in the tactic. The theorem
supplies three independent product inequalities and asks for their endpoints.

## Evidence

- Source revision: `097a4117c7f7038f8d448217d7836a0d95d41bbe`.
- Pinned toolchain: `leanprover/lean4:v4.35.0`.
- Exact build command: `cd lean && lake build Colony` — completed successfully
  (13 jobs; existing linter warnings were reported).
- Exact focused check: `cd lean && lake env lean Colony/Examples/OrderedProduct.lean`
  — exit code 0. The positive theorem compiled; the example's
  `fail_if_success` check compiled, establishing that the reversed goal was
  not solved by `colony` from only the reversed hypothesis.
- Assurance: Lean elaboration/kernel acceptance for this source file. No
  exported replay or independent-kernel check was run.

## Failed attempts

- `cd lean && lake env lean Colony/Examples/OrderedProduct.lean` before the
  initial library build failed with `unknown module prefix 'Colony'` because
  `Colony.Tactic.olean` did not exist yet. Building `Colony` first resolved
  the setup issue; this was not a proof failure.
- The reversed-direction goal is intentionally tested inside the example and
  is expected to fail tactic search; `fail_if_success` then closes the
  surrounding `True` goal. This negative check compiled successfully.

## Limitations

The result demonstrates chaining of supplied inequalities whose endpoints
are ordered-product expressions; it does not prove pointwise factor
monotonicity implies a product inequality. It is a bounded local experiment,
not evidence of broader tactic completeness or independent verification.
