# AUTO-4b88e8dd25: bounded equality-conditional splitting

## Scope and source

Base revision: `e520c39bbf6989f33dad692560babfaa49aed440`.
Reviewed candidate revision and current `HEAD`: `3a82fcfec75081ca4b6f01e4926e46e5f8d9572c` on `codex/colony-auto-4b88e8dd25-01922c18db54`.
The final corrections are uncommitted working-tree changes on that revision, as required for this worker. SHA-256 of the tested Lean source files:

| File | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `564cf2806af4aa3dc8c7661cb3541589b472fdf0556d7620d827171095b347ac` |
| `lean/Colony/Examples/RecursiveKeyedInvariant.lean` | `e1b4e41d46cea61a89e10ce9696be1398cf05d156139d8f2c14911b85fdb7916` |
| `lean/Colony.lean` | `190ee792c6bf52d0b2703819c8a58b0420d9afd4d3c6404f0796fac665b418bb` |

The final fixture proves `replaceKey_zero_sum` for every list and key using exactly `by colony`. Zeroing matching entries leaves the sum of nonmatching entries. The `sumExcept` recursion keeps the equality conditional around the recursive sum, so the induction step needs the equality split. A concrete case checks that both sides are 3 for `[2, 3, 2]` and key 2, and that the `+ 1` variant is false. A separate `fail_if_success` checks that `colony` does not prove that false variant for arbitrary list and key.

The splitter enumerates non-propositional local declarations in context order and pairs them in increasing index order. It attempts at most eight definitionally same-typed pairs per search node and has depth two. Each pair check starts with a tactic-state snapshot. A type mismatch restores it, and any failed `by_cases` candidate or failed branch restores it before trying the next pair. Branch leaves use the existing bounded `simp_all <;> omega` solver. No theorem-name dispatch or helper lemma was added.

## Experiments and exact commands

All Lean commands below ran from `lean/`; Git and checksum commands ran from the repository root. `lean/lean-toolchain` pins `leanprover/lean4:v4.35.0`; `lean --version` reported Lean 4.35.0, commit `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`.

- Review identified the first fixture as false: with `state = [0]`, `key = 0`, `value = 1`, its left side is 1 and right side is 0. Prior candidate runs of `lake build Colony` and `lake env lean Colony/Examples/RecursiveKeyedInvariant.lean` failed at that theorem, as recorded before this correction.
- `lake build Colony.Examples.RecursiveKeyedInvariant Colony` passed after a first valid zeroing fixture, but that fixture simplified without the split. It was revised to put the recursive sum inside the equality conditional.
- A weighted-sum fixture was tried with `lake build Colony.Examples.RecursiveKeyedInvariant` and failed: the current branch solver could not combine its multiplication terms with the induction hypothesis. It was removed rather than claiming success.
- `lake build Colony.Examples.RecursiveKeyedInvariant` passed with the final conditional fixture and the split enabled. A diagnostic edit temporarily replaced the structural induction's split call with `throwError "colony: split disabled for fixture check"`; the same build then failed at the positive theorem (`colony: the initial proof portfolio could not close this goal`). The original split call was restored before the final checks. This isolates the fallback's role in the positive proof.
- `lake build Colony` passed: 15 jobs, including `Colony.Examples.RecursiveKeyedInvariant` and the existing Colony targets. The build reported only existing unused-variable and unnecessary-`simpa` linter warnings, plus two unused-variable warnings in the new negative fixture.
- `lake build` passed: 17 jobs, including both default targets `Colony` and `SeedProofs`; it repeated the linter warnings and printed existing SeedProofs axiom reports.
- `lake env lean Colony/Examples/RecursiveKeyedInvariant.lean` passed with the two new unused-variable warnings.
- `printf 'import Colony.Examples.RecursiveKeyedInvariant\n#print axioms Colony.Examples.RecursiveKeyedInvariant.replaceKey_zero_sum\n' | lake env lean /dev/stdin` passed and reported: `'Colony.Examples.RecursiveKeyedInvariant.replaceKey_zero_sum' depends on axioms: [propext]`.
- The initial axiom-query form ending in `lake env lean -` failed because Lean treated `-` as a filename; `/dev/stdin` was used for the successful query.
- `git diff --check` passed. `git rev-parse HEAD` reported `3a82fcfec75081ca4b6f01e4926e46e5f8d9572c`.

## Assurance and limits

The positive theorem elaborated and was accepted by the pinned Lean kernel in the successful `lake build Colony` and direct Lean check. Its reported axiom dependency is `propext`; the proof uses no `sorry`, `admit`, new axiom, native evaluation axiom, or disabled kernel check. The false variant is rejected by `colony` under `fail_if_success`, and a concrete false instance is established with `decide`. These results are elaborator/kernel acceptance on this toolchain. They do not establish exported replay, independent-kernel acceptance, general tactic completeness or security against adversarial inputs, or correspondence to Cardano execution.
