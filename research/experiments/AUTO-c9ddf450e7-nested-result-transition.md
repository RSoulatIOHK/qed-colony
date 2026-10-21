# AUTO-c9ddf450e7: nested result transition splitting

## Scope and acceptance

This isolated example measures the existing `colony` tactic on `Option (Except
Failure Nat)`. The transition is unchanged: `none` adds three retries, an error
adds two, and a success adds its natural value plus one. The theorem retains the
full transition call and proves that every response advances the retry count.
The intended bounded demonstration is one tactic-controlled constructor split
of the outer `Option`, with the inner `Except` obligations handled separately.
A nearby stronger universal claim must be refuted by a concrete input.

## Experiments and findings

- With the full transition goal and a local proof of the `some` case, `colony`
  failed before the definition was unfolded. The command was `lake env lean
  Colony/Examples/NestedResultTransition.lean` from `lean/`; it exited 1 at the
  `colony` line with `colony: the initial proof portfolio could not close this
  goal`. This showed that the named `step` definition needed to be exposed.
- Adding `simp only [step] at *` before `colony` exposed the outer match. The
  source now runs `fail_if_success` on the tactic's exact initial arithmetic
  portfolio (`omega`, `simp_all <;> omega`, `decide`); it passes, showing that
  none of those alternatives closed the goal. The following `colony` call
  succeeds. Inspection of the unchanged `Colony.Tactic` implementation shows
  that its next applicable branch is `optionPortfolio`, which cases on the
  `Response` variable. Thus the tactic performs the outer `Option` constructor
  split at depth one. The proof does not demonstrate tactic-controlled splitting
  of the inner `Except` or the two `Failure` constructors. Local lemmas prove
  the distinct success and error obligations, using the full `step` definition.
- The stronger claim `∀ response retries, step retries response > retries + 3`
  is false. The source refutes it using `some (.ok 0)` with `retries = 0`;
  simplification of `step` yields the contradiction.

## Reproducible evidence

- Source revision: candidate `9bb9232adbd62a3e9595b5527262ab2f4ae073c8`
  with the uncommitted changes in this experiment. The original base revision
  was `6726233302f4fc7f9f3aeee745002813ef6b38bb`. The example source's
  SHA-256 at check time was
  `7b23291312d774591614fde7e7bc689dbe4b6e206cb78e67775d46005cdf3cd9`.
- Command from `lean/`: `lake env lean Colony/Examples/NestedResultTransition.lean`.
  Outcome with the working-tree source above: exit 0 with no diagnostics.
- Command from `lean/`: `lake build Colony.Examples.NestedResultTransition`.
  Outcome: exit 0, `Build completed successfully (4 jobs)`.
- Command from the repository root: `git diff --check`. Outcome: exit 0.
- Assurance: Lean elaborator kernel acceptance of this source file's proof
  terms. No exported replay, independent-kernel acceptance, or correspondence
  to Cardano execution was measured. The process exit code alone is not a
  separate proof certificate.
