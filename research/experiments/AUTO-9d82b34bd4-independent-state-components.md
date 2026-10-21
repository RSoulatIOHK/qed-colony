# AUTO-9d82b34bd4: compositional verification of independent state components

## Scope and exact model

Acceptance is a local, kernel-accepted proof of the original bounded theorem,
using the existing `colony` portfolio for the component obligations, together
with a mixed-command non-vacuity witness and a rejected false preservation
claim. Only this note and the example may change; the integration tactic stays
untouched. The retry retains the inherited model, theorem and bound. Before
additional measurement, its scope is to strengthen evidence with the complete
resulting state and a false claim carrying the same bounded-sequence premise.

Base source revision: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
Measured candidate commit: `3d07df3065ae81c00cc397d8fd79790b9b033ac9`,
with the uncommitted example-file revision identified by its SHA-256 below.
The example is `lean/Colony/Examples/IndependentStateComponents.lean`.
It defines the complete model as follows:

```lean
structure State where
  balance : Nat
  recorded : Nat
  deriving DecidableEq, Repr

inductive Command where
  | addBalance (amount : Nat)
  | addRecorded (amount : Nat)
  | skip
  deriving DecidableEq, Repr

def Bounded (bound : Nat) (commands : List Command) : Prop :=
  commands.length ≤ bound

def step (state : State) (command : Command) : State :=
  match command with
  | .addBalance amount => ⟨state.balance + amount, state.recorded⟩
  | .addRecorded amount => ⟨state.balance, state.recorded + amount⟩
  | .skip => state

def run (commands : List Command) (state : State) : State :=
  match commands with
  | [] => state
  | command :: rest => run rest (step state command)
```

Thus commands update the two fields independently. The original preservation
theorem, with no assumptions beyond the explicit sequence bound, is:

```lean
theorem bounded_run_balance_monotone (bound : Nat) (commands : List Command)
    (state : State) (_hbound : Bounded bound commands) :
    state.balance ≤ (run commands state).balance
```

The bound is on list length; command amounts remain arbitrary naturals. The
proof uses `colony` to close the arithmetic preservation obligation for each
constructor of the one-step field lemma. It then inducts over the sequence
and composes the inequalities. The bound is not needed for
monotonicity, but is retained as the requested bounded-sequence condition.

The file includes a concrete two-command bounded-sequence witness and result.
`mixed_updates_witness` additionally proves the entire resulting state is
`⟨4, 5⟩` from `⟨3, 3⟩`, so both independent fields actually change.
It also includes a false claim that `recorded` is unchanged by every sequence;
the counterexample applies `.addRecorded 1`. Separate `fail_if_success` checks
record that the unchanged `colony` tactic does not close the generic positive
target directly or the false claim.

```lean
Bounded 2 [.addBalance 1, .addRecorded 2]
(run [.addBalance 1, .addRecorded 2] ⟨3, 3⟩).balance = 4
run [.addBalance 1, .addRecorded 2] ⟨3, 3⟩ = ⟨4, 5⟩

-- Intentionally invalid:
∀ state : State, ∀ commands : List Command,
  (run commands state).recorded = state.recorded
-- Counterexample: state = ⟨0, 0⟩, commands = [.addRecorded 1].
```

The final file also guards and refutes the bounded version of the false claim:

```lean
∀ (bound : Nat) (commands : List Command) (state : State),
  Bounded bound commands → (run commands state).recorded = state.recorded
```

`bounded_recorded_preservation_false` instantiates `bound = 1`,
`commands = [.addRecorded 1]`, `state = ⟨0, 0⟩`; the premise holds and execution
gives `recorded = 1` instead of `0`. Thus length bounding does not rescue the
invalid claim. Neither false proposition is asserted as a theorem; their
negations are proved and their tactic attempts are guarded with
`fail_if_success`.

## Source identity and experiment

- Base revision: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
- Measured candidate commit: `3d07df3065ae81c00cc397d8fd79790b9b033ac9`;
  the measurements below include the uncommitted example-file change.
- Final example SHA-256: `655a049cc9020344c938fd49fc55f529b6df0b0d33c362765dcccca299636403`.
- Pre-strengthening example SHA-256: `878bcf6d961d1e4dbb1e1976aecd9206c82918f17aa4e46f56ca990747980632`.
  The seed evaluator and standalone direct probes below measured this version;
  the final build, direct file check and axiom audit measured the final version.
  Only witnesses and bounded negative checks were added between these versions.
- `lean/Colony/Tactic.lean` SHA-256 at measurement: `2865f270c73f08c27abbc4f79dabd2ff5e312d8bb4aa6660e835af0fc10be5b6` (unchanged during this experiment).
- Command: `cd lean && lake env lean --version`.
- Outcome: Lean 4.35.0, compiler commit `eb6cafb7290e8bd5f2937522d8d804f58f02bafc`, release build.
- Command: `cd lean && lake build Colony.Examples.IndependentStateComponents`
- Outcome: exit 0; `Build completed successfully (4 jobs)`.
- Command: `cd lean && lake env lean Colony/Examples/IndependentStateComponents.lean`
- Outcome: exit 0, with no warnings after the example-local unused-variable fix.
- Command: generate a temporary Lean file importing the example and run
  `#print axioms` on `step_balance_monotone` and
  `bounded_run_balance_monotone`, `mixed_updates_witness` and
  `bounded_recorded_preservation_false` via `lake env lean`.
- Outcome: exit 0; all four declarations depend only on
  `[propext, Quot.sound]`. The temporary audit file contained the example import
  followed by `#print axioms Colony.Examples.IndependentStateComponents.<name>`
  for each listed declaration.
- Command: `node --check observatory/dist/app.js`
- Outcome: exit 0.
- Command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`
- Outcome: exit 1; 286 tests ran, with 2 failures and 13 errors. Reported
  errors included sandbox-denied `ps` process inspection and local socket
  binding. The two failed assertions were
  `test_unverifiable_cleanup_keeps_process_record_and_worker_slot` (missing
  process record) and
  `test_actual_triage_outage_reconnects_after_restart_and_replays_completed_handoff`
  (`needs_review` versus `waiting_network`). These controller/sandbox results
  are separate from the Lean acceptance result; the full Python suite did not
  pass. No controller code was changed.
- Command: `python3 scripts/evaluate_lean.py --output <temporary report>`,
  with stdout/stderr redirected to a temporary log; all default strategies ran.
- Outcome: exit 0; the pilot seed-suite summary reported `colony`
  `positive_certified = 8/8`, with the intentional negative check rejected
  and its witnesses accepted; zero timeouts and evidence errors for every
  strategy. Other positive totals were `simp = 4/8`, `omega = 1/8`,
  `grind = 1/8`. These are pilot labels, not independent certification.
  This new example is not a scored comparator case.
- Commands: `git diff --check` and
  `git diff 702a19c205d6304b5a97eb81fb6876ef119e5567 -- lean/Colony/Tactic.lean`.
- Outcomes: exit 0 with no whitespace errors; no shared-tactic changes from
  the requested base. Only the permitted example and research note were edited.

The inherited attempt notes report the following failures (not re-created in
this retry): the nil induction case
needed `Nat.le_refl`; the length-bound induction hypothesis required deriving
`rest.length ≤ bound` from `rest.length + 1 ≤ bound`; and the first non-vacuity
formulation lacked decidable proposition reduction for `Bounded`. These were
fixed without changing the preservation target. The guarded check confirms
only that the portfolio does not close this generic custom-state
recursive-list goal directly in the stated context. The tactic source has a
structural-induction fallback for List and Nat locals; the guarded check does
not establish whether it attempted induction or why the search failed. The
theorem succeeds by an explicit induction composed with the `colony`-proved
one-step lemma. The false claim also fails under a guarded `colony` attempt
and is separately refuted by the concrete command. No change was made to
`colony` or its shared tactic source.

### Direct retry probes

Each temporary file imports `Colony.Examples.IndependentStateComponents` and
opens `Colony.Examples.IndependentStateComponents`. The positive probe uses
the original statement verbatim:

```lean
example (bound : Nat) (commands : List Command)
    (state : State) (_hbound : Bounded bound commands) :
    state.balance ≤ (run commands state).balance := by
  colony
```

The intentionally invalid probe carries the same length-bound premise:

```lean
example : ∀ (bound : Nat) (commands : List Command) (state : State),
    Bounded bound commands → (run commands state).recorded = state.recorded := by
  colony
```

Commands, from `lean/`: `lake env lean <temporary DirectPositive.lean>` and
`lake env lean <temporary DirectBoundedNegative.lean>`, using fresh files
created by Python `tempfile.TemporaryDirectory` and `subprocess.run` with a
30-second timeout. Both returned exit 1 with exactly the tactic diagnostic
`colony: the initial proof portfolio could not close this goal` (at line 6,
column 2 and line 5, column 2 respectively). These are expected proof failures,
not import errors or timeouts. No model, command, assumption, bound or positive
theorem statement was changed in response.

Source inspection explains the scope of the available automation without
claiming an execution trace: the dedicated command/list branch recognizes
`Colony.Procedure.ListCommand` and unfolds that procedure's `process`/`step`;
this example uses a distinct `Command` and `run`. The generic List/Nat fallback
exists but does not explicitly unfold these custom definitions or split this
custom command type. No per-branch trace was collected, so the diagnostic does
not establish which induction attempts ran or their individual failure causes.

## Assurance and limits

The successful Lean build means the positive proof, witness, and invalid-claim
counterexample were accepted by Lean's elaborator/kernel. `colony` closes the
one-step lemma used by the theorem, but does not directly close the generic
bounded theorem in the guarded attempt. No exported replay, independent-kernel check, or correspondence
to Cardano execution was performed. This is a local proof example, not a
benchmark or security-boundary claim.
