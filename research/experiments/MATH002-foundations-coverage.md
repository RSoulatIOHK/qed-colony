# MATH002: foundational mathematics single-call coverage

## Predeclared matrix

Starting reviewed revision: `929ec986830a8ed0d31c2b73cb737334fc86c47d`.

Before any tactic attempt, the fixed matrix is:

| ID | Category | Exact proposition |
|---|---|---|
| A1 | Nat addition identity | `∀ (n : Nat), n + 0 = n` |
| A2 | Nat addition identity | `∀ (n : Nat), 0 + n = n` |
| A3 | Nat addition permutation | `∀ (x y : Nat), x + y = y + x` |
| A4 | Nat addition association | `∀ (x y z : Nat), (x + y) + z = x + (y + z)` |
| O1 | Order implication | `∀ (x y z : Nat), x ≤ y → x + z ≤ y + z` |
| L1 | List length/append | `∀ (xs ys : List Nat), (xs ++ ys).length = xs.length + ys.length` |
| L2 | List reverse length | `∀ (xs : List Nat), xs.reverse.length = xs.length` |
| L3 | List reverse involution | `∀ (xs : List Nat), xs.reverse.reverse = xs` |

Fresh binders are used exactly as shown. Statements and bounds are fixed for the experiment. Controls, excluded from coverage score: invalid arithmetic `∀ (n : Nat), n + 1 = n`, with counterexample `n = 0`; invalid list claim `∀ (xs : List Nat), xs.length = 0`, with counterexample `xs = [0]`. Non-vacuity witnesses: `1 + 1 = 2` and `([0] : List Nat).length = 1`, both attempted using exactly `by colony`.

## Method

Each target/control is evaluated independently by the installed Lean toolchain with `import Colony.Tactic` and proof body exactly `by colony`. A target is placed in the imported coverage module only when that exact attempt succeeds. Failure attempts use a temporary source harness and their full generated source and Lean output are retained below. No result from another example or helper theorem is imported. Successful acceptance is Lean elaborator/kernel acceptance in this build only, not exported replay, independent-kernel acceptance, or correspondence to Cardano execution. This is an engineering measurement, not an official benchmark score.

## Outcomes

Attempted every matrix case once after building `Colony.Tactic`. A1–A4, O1, L1–L3 all succeeded with exactly the proof bodies shown below; they are included in `lean/Colony/Examples/FoundationsCoverage.lean`. Both intentionally false claims failed with the tactic's terminal error. Both concrete non-vacuity witnesses succeeded. Controls are not included in the coverage count. No proof failed due to resource exhaustion; there was no timeout. Initial attempts before building the imported module failed at module resolution (`unknown module prefix 'Colony'`); these are harness/build setup failures, not target outcomes, and were discarded before the measured attempts. The prerequisite build then succeeded.

| ID | Outcome | Raw proof declaration |
|---|---|---|
| A1 | proof accepted | `theorem math002_A1 (n : Nat) : n + 0 = n := by colony` |
| A2 | proof accepted | `theorem math002_A2 (n : Nat) : 0 + n = n := by colony` |
| A3 | proof accepted | `theorem math002_A3 (x y : Nat) : x + y = y + x := by colony` |
| A4 | proof accepted | `theorem math002_A4 (x y z : Nat) : (x + y) + z = x + (y + z) := by colony` |
| O1 | proof accepted | `theorem math002_O1 (x y z : Nat) : x ≤ y → x + z ≤ y + z := by colony` |
| L1 | proof accepted | `theorem math002_L1 (xs ys : List Nat) : (xs ++ ys).length = xs.length + ys.length := by colony` |
| L2 | proof accepted | `theorem math002_L2 (xs : List Nat) : xs.reverse.length = xs.length := by colony` |
| L3 | proof accepted | `theorem math002_L3 (xs : List Nat) : xs.reverse.reverse = xs := by colony` |
| CTRL-ARITH | expected rejection (`proof_failed`) | `theorem math002_invalid_arith (n : Nat) : n + 1 = n := by colony` |
| CTRL-LIST | expected rejection (`proof_failed`) | `theorem math002_invalid_list (xs : List Nat) : xs.length = 0 := by colony` |
| CTRL-NAT-WITNESS | proof accepted (non-vacuity) | `theorem math002_witness_nat : 1 + 1 = 2 := by colony` |
| CTRL-LIST-WITNESS | proof accepted (non-vacuity) | `theorem math002_witness_list : ([0] : List Nat).length = 1 := by colony` |

## Failure evidence: complete generated source and diagnostics

Each source was independently generated with `import Colony.Tactic`, a blank line, the declaration below, and a final newline. These are complete source files.

### CTRL-ARITH

```lean
import Colony.Tactic

theorem math002_invalid_arith (n : Nat) : n + 1 = n := by colony
```

Lean diagnostic (exit 1):

```text
<generated-source>:3:58: error: colony: the initial proof portfolio could not close this goal
```

Counterexample data: `n = 0`, yielding `1 = 0`.

### CTRL-LIST

```lean
import Colony.Tactic

theorem math002_invalid_list (xs : List Nat) : xs.length = 0 := by colony
```

Lean diagnostic (exit 1):

```text
<generated-source>:3:67: error: colony: the initial proof portfolio could not close this goal
```

Counterexample data: `xs = [0]`, yielding `1 = 0`.

## Non-vacuity and successful dependencies

Non-vacuity sources, each independently attempted with exactly the displayed proof:

```lean
import Colony.Tactic

theorem math002_witness_nat : 1 + 1 = 2 := by colony
```

```lean
import Colony.Tactic

theorem math002_witness_list : ([0] : List Nat).length = 1 := by colony
```

Both Lean invocations exited 0 with no diagnostics. `#print axioms` after importing `Colony.Examples.FoundationsCoverage` reported:

```text
'math002_A1' depends on axioms: [propext, Quot.sound]
'math002_A2' depends on axioms: [propext, Quot.sound]
'math002_A3' depends on axioms: [propext, Quot.sound]
'math002_A4' depends on axioms: [propext, Quot.sound]
'math002_O1' depends on axioms: [propext, Quot.sound]
'math002_L1' depends on axioms: [propext]
'math002_L2' depends on axioms: [propext]
'math002_L3' depends on axioms: [propext]
```

These are Lean's reported dependencies; no `sorry`, `admit`, or custom axiom was introduced.

## Reproduction record and assurance

- Starting revision and tactic implementation: `929ec986830a8ed0d31c2b73cb737334fc86c47d` (workspace `HEAD` at start; `lean/Colony/Tactic.lean` was not changed).
- Toolchain: repository `lean/lean-toolchain`, `leanprover/lean4:v4.35.0`.
- Commands: `lake build Colony.Tactic`; independently for each source, `lake env lean <generated-source>`; after adding the coverage module, `lake build Colony`; axiom query via `lake env lean --stdin` with `import Colony.Examples.FoundationsCoverage` and the eight `#print axioms` commands; final full project check `lake build`.
- The initial independent source run preceded the prerequisite build and produced `unknown module prefix 'Colony'` for each case. `lake build Colony.Tactic` succeeded, after which the measured rerun produced the outcomes above.
- `lake build Colony` and final `lake build` succeeded. The latter built/replayed all 16 jobs; existing unrelated linter warnings were emitted.
- Coverage measured: 8/8 predeclared ordinary propositions accepted in one tactic call. This is a small declared coverage matrix, not a new official benchmark score. Assurance is elaborator/kernel acceptance by this Lean build. No exported replay or independent-kernel check was performed, and no claim of correspondence to Cardano execution is made.
