# AUTO-e4a17d93ee: bounded induction for the list-state invariant

## Scope and source

Base revision: `e1892b16c65d85d960b079970c5547cc050bb978`.
Tested implementation head: `80ec928b6cd5220b44434c79194457e38f82a1cd`.
The evidence update to this note and its evaluator artifact is uncommitted, as required for this worker. The evaluator recorded these SHA-256 hashes for the tested Lean source snapshot:

| Source | SHA-256 |
| --- | --- |
| `lean/Colony/Tactic.lean` | `dd791fb3fe6b6033a61ae0049720680f3d89223f8aca38feeb8edcf61e67c1a0` |
| `lean/Colony/Examples/ListStateInvariant.lean` | `238cc163f60b8187863f820b49ab311bd5635acb2d2785fe55ee69a8ab6885ee` |
| `lean/Colony/Examples/BooleanBranching.lean` | `98523ebd094b67d935d3a38799c758be76cb2a5b28bb0ef4610e8a9663df5c4a` |
| `lean/Colony/Procedures/ListState.lean` | `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0` |
| `lean/Colony.lean` | `78a837406c846b4192085c1548d00b242abf5917d554ad56979c1ec8ac777dda` |

The complete evaluator report records hashes for every Lean source it read, the manifest and challenge lock, each generated declaration, each Lean output, and the summary: [AUTO-e4a17d93ee-evaluator.json](AUTO-e4a17d93ee-evaluator.json).
The project toolchain is Lean `v4.35.0` (`lean/lean-toolchain`). The theorem statement, `process` definition, assumptions, and false sequence-property control are unchanged. The theorem body now invokes `by colony`.

The new candidate runs only when exactly one local declaration has type `List ListCommand`. It structurally inducts on that declaration and generalizes the other non-propositional local declarations. Each branch uses the fixed solver `simp_all [Colony.Procedure.process, Colony.Procedure.step] <;> omega`; if the initial branch attempt fails, it splits a local `ListCommand` and applies that same solver. The full candidate is wrapped in saved-state restoration, so any failure returns to the pre-candidate tactic state.

## Failed attempts and diagnostics

An initial implementation tried to filter the local context with `LocalContext.filterM` and failed to compile. Lean reported:

```text
Invalid field `filterM`: The environment does not contain `Lean.LocalContext.filterM`
```

It was replaced with an explicit context loop.

The first induction helper hard-coded the generalized binder name `state`. A build failed with:

```text
error: Colony/Examples/ListStateInvariant.lean:27:2: Unknown identifier `state✝`
```

The generated binder name was inaccessible under that syntax. The helper now obtains all eligible generalized identifiers from the local context.

The next branch shape attempted only `simp_all [process, step] <;> omega`. The observed induction goals were:

```text
case nil
state : ListState
h : state.balance = state.recorded
⊢ (process [] state).balance = (process [] state).recorded

case cons
head✝ : ListCommand
tail✝ : List ListCommand
tail_ih✝ : ∀ (state : ListState), state.balance = state.recorded →
  (process tail✝ state).balance = (process tail✝ state).recorded
state : ListState
h : state.balance = state.recorded
⊢ (process (head✝ :: tail✝) state).balance = (process (head✝ :: tail✝) state).recorded
```

The cons case needs command constructor splitting before simplification. Since Lean generates inaccessible names such as `head✝`, the solver now discovers the local command declaration rather than referring to a source-level name. Before that adjustment, the externally visible tactic diagnostic was:

```text
error: Colony/Examples/ListStateInvariant.lean:27:2: colony: the initial proof portfolio could not close this goal
```

## Commands and outputs

Commands were run from the `lean/` project directory unless stated otherwise.

```sh
lake build Colony
```

After the induction candidate was complete:

```text
✔ [3/8] Built Colony.Tactic
✔ [4/8] Built Colony.Examples.BooleanBranching
✔ [5/8] Built Colony.Examples.ListStateInvariant
✔ [6/8] Built Colony.Seeds
✔ [7/8] Built Colony
Build completed successfully (8 jobs).
```

```sh
lake build
```

```text
✔ [6/10] Replayed Colony.Examples.ListStateInvariant
✔ [9/10] Built SeedProofs
Build completed successfully (10 jobs).
```

The full build also prints expected axiom reports for unrelated `SeedProofs` examples. The target theorem was checked separately:

```sh
lake env lean --stdin <<'EOF'
import Colony.Examples.ListStateInvariant
#print axioms Colony.Examples.process_preserves_list_state_invariant
EOF
```

Output:

```text
'Colony.Examples.process_preserves_list_state_invariant' depends on axioms: [propext]
```

`propext` is Lean's standard propositional extensionality axiom; no `sorry`, `admit`, arbitrary axiom, native evaluation axiom, or disabled kernel check was introduced. The false sequence-property remains inside `fail_if_success` and the project build succeeds with that guard in place.

From the repository root, `git diff --check` completed with exit code 0 and no output.

The review requested an unchanged evaluator run because the default Lake targets do not compile its generated R003 frontier. From the repository root:

```sh
python3 scripts/evaluate_lean.py --output /tmp/AUTO-e4a17d93ee-evaluator.json
cp /tmp/AUTO-e4a17d93ee-evaluator.json research/experiments/AUTO-e4a17d93ee-evaluator.json
```

The evaluator exited 0 after `Build completed successfully (10 jobs).` Its colony rows were:

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

The exact colony summary was `positive_certified: 8`, `positive_total: 8`, `unsupported_certified: 1`, `timeouts: 0`, and `evidence_errors: 0`. For `false_shared_payment_safety`, `rejected`, `positive_witnesses_certified`, and `sanity_pass` were all `true`. The R003 declaration's axiom output was `'benchmark_reverse_involution_frontier' depends on axioms: [propext]`. The false case produced `colony: the initial proof portfolio could not close this goal`; its failed declaration was not certified, despite Lean printing a `sorryAx` dependency while reporting the error. The complete JSON also records the unchanged `simp`, `omega`, and `grind` baseline results.

Additional checks from the repository root:

```sh
node --check observatory/dist/app.js
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p 'test_evaluate_lean.py' -v
```

The Node check exited 0 with no output. The broad Python suite exited 1: `Ran 286 tests in 76.080s`, `FAILED (failures=2, errors=13)`. The errors arise in controller process and HTTP server tests under this sandbox: `ps` and local socket binding returned `PermissionError: [Errno 1] Operation not permitted`. Two controller assertions also failed. Those failures are outside the Lean candidate and limit the broad-suite result; the Lean build and evaluator completed independently. The focused evaluator tests exited 0: `Ran 12 tests in 0.061s`, `OK`.

## Assurance and limits

The build and unchanged evaluator provide ordinary Lean elaborator kernel acceptance for the theorem, one-step and Boolean examples, and the generated R003 frontier. The theorem's axiom report contains only `[propext]`. The local evaluator is a pilot, not a tamper-proof security boundary. No exported replay, independent-kernel acceptance, or correspondence to Cardano execution is claimed. The tactic is deterministic and local, and this candidate is deliberately narrow: it requires exactly one visible `List ListCommand` local declaration and generalizes other non-propositional locals. The existing generic induction portfolio remains separate. The candidate saves tactic state before induction and restores it if any branch fails.
