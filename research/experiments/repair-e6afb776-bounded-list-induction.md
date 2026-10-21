# REPAIR-e6afb776: bounded list induction and evaluator evidence

## Source and scope

Base revision: `d1450e0f9dfa1170ce157c9ff32cf1d046b13b59`.
Source implementation inspected: public candidate head `ddce64af4f0f02babdf9b25d053b3f9304ff6e68` (the working copy had this commit object locally). The repaired source is based on the stated base revision; no commit was created. The theorem statement, `process` definition, assumptions, existing examples, and false sequence-property control are preserved. The sequence-invariant theorem body is now `by colony`.

The candidate considers exactly one visible local whose type is `List ListCommand`. It inducts on that list, generalizes other non-propositional locals, and applies the fixed branch solver `simp_all [Colony.Procedure.process, Colony.Procedure.step] <;> omega`. On a branch where this solver fails, it finds a visible `ListCommand` local, cases on it, and applies the same solver to the resulting branches. The whole candidate uses saved tactic state and restores it on failure.

SHA-256 of the exact Lean source snapshot consumed by the unchanged evaluator:

| Source | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `2865f270c73f08c27abbc4f79dabd2ff5e312d8bb4aa6660e835af0fc10be5b6` |
| `lean/Colony/Examples/ListStateInvariant.lean` | `10746c7bc8ee2ce9ba403c269c994b4baa47fe45cccae61bf64715a52b9762e8` |
| `lean/Colony/Examples/BooleanBranching.lean` | `98523ebd094b67d935d3a38799c758be76cb2a5b28bb0ef4610e8a9663df5c4a` |
| `lean/Colony/Examples/OptionBranching.lean` | `faee719665bb2d908a58dc4969fa8d56a9208041bc77873525d1eb71828754fa` |
| `lean/Colony/Procedures/ListState.lean` | `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0` |
| `lean/Colony.lean` | `9a0b2cdeae4445542f4dc480c5994f35f760e81277a7c42648eb4db77f5355c0` |

The evaluator JSON records hashes for every Lean source, challenge/configuration input, generated declaration, and result: [complete evaluator report](repair-e6afb776-evaluator.json).

## Checks and outputs

Command, from `lean/`:

```sh
lake build Colony.Examples.ListStateInvariant Colony.Examples.BooleanBranching Colony.Examples.OptionBranching
```

Output: `Build completed successfully (6 jobs).` Only existing unused-variable linter warnings appeared. This directly elaborated the sequence theorem with `by colony`, one-step and Boolean branching examples, the false sequence control, and option branching examples.

Command, from repository root (unchanged evaluator):

```sh
python3 scripts/evaluate_lean.py --output /tmp/repair-e6afb776-evaluator.json
```

The command exited 0 and wrote the complete report copied to `research/experiments/repair-e6afb776-evaluator.json`. The `colony` results were:

```text
colony   arithmetic_monotonicity                  certified
colony   reverse_accumulator_length               certified
colony   count_accumulator_invariant              certified
colony   recursive_program_nonvacuity             certified
colony   account_state_invariant                  certified
colony   allocated_payments_cover_sales           certified
colony   allocated_payments_nonvacuity            certified
colony   shared_payment_attack_witness            certified
colony   false_shared_payment_safety              proof_failed
colony   reverse_involution_frontier              certified
```

Evaluator summary: `positive_certified: 8`, `positive_total: 8`, `unsupported_certified: 1`, `timeouts: 0`, `evidence_errors: 0`. For the negative control, `rejected`, `positive_witnesses_certified`, and `sanity_pass` are all `true`. The R003 `reverse_involution_frontier` declaration has axiom output `[propext]`. The unchanged baselines reported: `simp` 4/8 positives, `omega` 1/8, and `grind` 1/8 with one timeout. The JSON has all exact outputs for these rows.

`git diff --check` exited 0 with no output.

## Failed candidate shape

A direct list induction that did not generalize `state` failed. Reproduction command: `lake env lean /tmp/FailedListInduction.lean`, using `ListState.lean` and the original sequence target, with `induction commands` and the cons branch applying the induction hypothesis. Lean diagnostic:

```text
Tactic `apply` failed: could not unify the type of `ih`
  (process commands state).balance = (process commands state).recorded
with the goal
  (process commands (step state command)).balance = (process commands (step state command)).recorded

case cons
state : ListState
h : state.balance = state.recorded
command : ListCommand
commands : List ListCommand
ih : (process commands state).balance = (process commands state).recorded
⊢ (process commands (step state command)).balance = (process commands (step state command)).recorded
```

This is why the implemented candidate generalizes the other non-propositional local state before induction.

## Assurance and limits

The Lean build and evaluator establish ordinary Lean elaborator kernel acceptance for the direct theorem proof and the reported evaluator declarations. The evaluator's `colony` results are deterministic local pilot evidence. The report identifies the R003 declaration's axiom dependency as `[propext]`; no arbitrary axioms, `sorry`, `admit`, or disabled kernel checks were introduced. No exported replay, independent-kernel acceptance, tamper-proof evaluator assurance, or correspondence to Cardano execution is established. The evaluator is unchanged but remains a local pilot, not an externally controlled security boundary.
