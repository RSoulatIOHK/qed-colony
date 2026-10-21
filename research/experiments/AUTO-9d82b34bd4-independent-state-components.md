# AUTO-9d82b34bd4: compositional verification of independent state components

## Scope and exact model

Base source revision: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
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
proof decomposes the property into a one-step field lemma, then inducts over the
sequence and composes the inequalities. The bound is not needed for
monotonicity, but is retained as the requested bounded-sequence condition.

The file includes a concrete two-command bounded-sequence witness and result.
It also includes a false claim that `recorded` is unchanged by every sequence;
the counterexample applies `.addRecorded 1`. A `fail_if_success` check records
that the unchanged `colony` tactic does not prove the original positive target
in the stated context.

## Source identity and experiment

- Base revision: `702a19c205d6304b5a97eb81fb6876ef119e5567`.
- Final example SHA-256: `b0883e46c3da7bd6e193c9adbf858c4020531cac18aeef69c9e918c43923c7ea`.
- `lean/Colony/Tactic.lean` SHA-256 at measurement: `2865f270c73f08c27abbc4f79dabd2ff5e312d8bb4aa6660e835af0fc10be5b6` (unchanged during this experiment).
- Command: `cd lean && lake build Colony.Examples.IndependentStateComponents`
- Outcome: exit 0; `Build completed successfully (4 jobs)`. Lean emitted one unused-parameter warning in the guarded negative check.
- Command: `cd lean && lake env lean Colony/Examples/IndependentStateComponents.lean`
- Outcome: exit 0 with the same unused-parameter warning.

Earlier implementation attempts failed during checking: the nil induction case
needed `Nat.le_refl`; the length-bound induction hypothesis required deriving
`rest.length ≤ bound` from `rest.length + 1 ≤ bound`; and the first non-vacuity
formulation lacked decidable proposition reduction for `Bounded`. These were
fixed without changing the preservation target. The final `fail_if_success`
check confirms the portfolio limitation: its proof search cannot establish
this generic custom-state recursive-list theorem. The proof succeeds by an
explicit induction composed with the one-step lemma; no change was made to
`colony` or its shared tactic source.

## Assurance and limits

The successful Lean build means the positive proof, witness, and invalid-claim
counterexample were accepted by Lean's elaborator/kernel. It does not show that
`colony` proves the preservation theorem; the guarded check shows the opposite
for this goal. No exported replay, independent-kernel check, or correspondence
to Cardano execution was performed. This is a local proof example, not a
benchmark or security-boundary claim.
