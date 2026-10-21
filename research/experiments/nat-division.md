# Generic Nat division and remainder probe

## Source revision and scope

- Starting source revision: `b94b650d58581ed7aaabee86da0c94b404a66a46`.
- The working branch was `codex/colony-auto-49f1c9ddd8-26c7a8efdb1a`.
- Changed files: `lean/Colony/Tactic.lean`, `lean/Colony/Examples/NatDivision.lean`, and `lean/Colony.lean`.
- Lean toolchain: `leanprover/lean4:v4.35.0`.

## Probe and implementation

The existing arithmetic portfolio tries bounded order search, `omega`, `simp_all <;> omega`, `ac_rfl`, and `decide`. A standalone probe showed that this portfolio cannot prove these generic goals:

```lean
(n d : Nat) : n % (d + 1) < d + 1
(n d : Nat) : n / (d + 1) ≤ n
```

The tactic now tries two direct library rules after its existing bounded order search and before its existing arithmetic fallback: `Nat.mod_lt` with `omega` discharging positivity, and `Nat.div_le_self`. This adds no expression search, recursion, or branching. It inherits the existing fixed behavior of `omega`; the only division-specific alternatives are these two fixed applications.

The new independent examples retain these exact theorem statements and close with exactly `by colony`:

```lean
theorem nat_mod_lt_succ (n d : Nat) : n % (d + 1) < d + 1 := by colony
theorem nat_div_le_self_succ (n d : Nat) : n / (d + 1) ≤ n := by colony
```

The false nearby target is `0 % (0 + 1) < 0`. The file uses `fail_if_success (have : 0 % (0 + 1) < 0 := by colony)` and then proves its negation by `decide`.

## Attempts and outcomes

- Initial standalone probe with the existing tactic failed on both generic theorems with `colony: the initial proof portfolio could not close this goal`.
- A reconstruction probe for `n = n / (d + 1) * (d + 1) + n % (d + 1)` caused the existing simplification fallback to hit Lean's maximum recursion depth. It was not added as a target or as a new tactic capability.
- The first version of the false-target example asked Lean to prove the false proposition itself after `fail_if_success`; the follow-on `omega` correctly reported a possible counterexample. The check was corrected to guard the false proof attempt inside a provable negation.
- After the change, `cd lean && lake env lean Colony/Examples/NatDivision.lean` exited successfully and printed:

```text
'Colony.Examples.nat_mod_lt_succ' depends on axioms: [propext, Quot.sound]
'Colony.Examples.nat_div_le_self_succ' depends on axioms: [propext]
```

- `cd lean && lake build Colony` completed successfully with `Build completed successfully (15 jobs).` Existing linter warnings in other example files were emitted during the build.

## Assurance and limits

The checked facts are Lean 4.35.0 elaboration/build acceptance of these example proof terms, successful execution of the false-target guard, and the stated `#print axioms` results. This establishes kernel-checked Lean proofs under the configured toolchain, with the listed standard axioms. It does not establish exported replay, acceptance by an independent kernel, correspondence to Cardano execution, or performance. Generic quotient/remainder reconstruction remains unsupported by this probe; no broader completeness claim is made.
