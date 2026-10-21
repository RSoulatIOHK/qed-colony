# Bounded Sum branching for state-transition proofs

## Scope and acceptance

The existing deterministic `Sum` fallback in `Colony.Tactic` scans visible local
declarations in context order, tries one candidate at a time, and requires the
existing arithmetic portfolio to close both constructor branches. This review
repairs the example and its evidence. The acceptance target is a transition
invariant proved by `by colony` with the input bound intact, a well-formed false
target rejected by `fail_if_success`, reachable witnesses for both constructors,
and an axiom report.

## Exact source identity

- Base revision: `3a7c71e41ba1a29df363e8847fbe5a01e3a96bf8`.
- Candidate HEAD: `70206c905854b68e225276ea8dfa55b145ec6496`.
- The final checks ran on that HEAD plus one uncommitted example correction; no
  new revision was created. Git blob IDs from `git hash-object` identify the
  exact tested Lean source: `lean/Colony/Tactic.lean`
  `229f0f61794083d8a564da80d1f31cdce1531c32`, `lean/Colony.lean`
  `0c4dfde06d5fdf811e67a5ef3949cd963f914d14`, and
  `lean/Colony/Examples/SumStateTransition.lean`
  `3c55f2c178c33fe952048389e9513a3433303b1f`.
- The committed candidate example has blob
  `feb91c1fd80b82440ef6c1446cdfbe7f2f7e4365`; it contains the erroneous
  `result` reference under a `_result` binder.
- Toolchain: repository `lean/lean-toolchain`, `leanprover/lean4:v4.35.0`.

## Result and commands

`step_advances_count` states that the payload returned by `step count advance`
is greater than the original `count` for either constructor. Its statement is
proved directly by `by colony`. `result_shape_advances_count` states the same
input-relative invariant for a local `Sum` result, assuming the constructor's
update equation from `step`; it exercises the local `Sum` split with `by colony`.
The `step 4 true = .inl 5` and `step 4 false = .inr 6` witnesses close by `rfl`.
The `fail_if_success` guard now refers to its bound `_result`; the `.inl 0`
counterexample independently establishes that the guarded bound is false.

- `git show HEAD:lean/Colony/Examples/SumStateTransition.lean | lake env lean --stdin`
  from `lean/`: exit 0 on the committed candidate; its only axiom report was
  `payload_successor_exceeds_itself: [propext, Quot.sound]`. This result did
  **not** validate the old negative guard, which failed elaboration on the
  unbound `result` name.
- `lake build` from `lean/` on the corrected working tree: exit 0, 13 jobs,
  `Build completed successfully (13 jobs).` The example reported no warnings;
  warnings from the Option, list, and accumulator examples were replayed.
- `lake env lean Colony/Examples/SumStateTransition.lean` from `lean/` on the
  same source: exit 0. It printed the two axiom reports below and no errors.
- `git diff --check`: exit 0. A forbidden-token scan over the tactic and
  example found no `sorry`, `admit`, or axiom declaration.

## Failed attempts

- The previous example's negative guard used `result` while binding `_result`.
  The committed candidate's successful elaboration was therefore a false
  negative test; the guard is corrected above.
- An initial `true_result_advances_count` theorem used
  `h : result = step count true` and tried `by colony`. `lake build` exited 1:
  `colony: the initial proof portfolio could not close this goal`. A direct
  diagnostic `cases result <;> simp_all [step]` left the equality unchanged in
  both branches, so `omega` could not prove the bound. That theorem was removed
  rather than weakening its statement or claiming success.
- A further reachable-result variant with
  `h : result = step count true ∨ result = step count false` also failed the
  standalone Lean check with the same portfolio error and was removed. The
  accepted input-relative theorem uses `step count advance` directly.

## Axioms and assurance

```text
'Colony.Examples.SumStateTransition.step_advances_count' depends on axioms: [propext]
'Colony.Examples.SumStateTransition.result_shape_advances_count' depends on axioms: [propext, Quot.sound]
```

These are Lean's standard logical axioms. No `sorry`, `admit`, custom axiom,
native evaluation axiom, or disabled kernel check was used. Assurance achieved:
Lean elaborator/kernel acceptance in the repository build. Exported replay,
independent-kernel acceptance, and correspondence to Cardano execution were not
checked.
