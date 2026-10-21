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

Each target/control is evaluated independently by the installed Lean toolchain with `import Colony.Tactic` and proof body exactly `by colony`. A target is placed in the imported coverage module only when that exact attempt succeeds. Each independent attempt uses a temporary source harness; complete regenerated sources and the captured Lean outputs are retained below. No result from another example or helper theorem is imported. Successful acceptance is Lean elaborator/kernel acceptance in this build only, not exported replay, independent-kernel acceptance, or correspondence to Cardano execution. This is an engineering measurement, not an official benchmark score.

## Outcome and evidence status

The first historical invocation preceded `lake build Colony.Tactic`. Its per-case source files and full output were discarded in that run; only the reported `unknown module prefix 'Colony'` summary survives. Those exact historical bytes cannot be recovered. To address the retention gap, the same 12 declarations were generated again and run twice: once with an isolated empty `LEAN_PATH` to reproduce the module-resolution failure, then through `lake env lean` with the tactic available. The reproduced setup failures below are new observations, not a claim that the lost original diagnostics were captured. The valid rerun is the measured coverage result.

| ID | Isolated module-path run | Measured Lake run |
|---|---|---|
| A1 | harness/build failure (exit 1) | proof accepted (exit 0) |
| A2 | harness/build failure (exit 1) | proof accepted (exit 0) |
| A3 | harness/build failure (exit 1) | proof accepted (exit 0) |
| A4 | harness/build failure (exit 1) | proof accepted (exit 0) |
| O1 | harness/build failure (exit 1) | proof accepted (exit 0) |
| L1 | harness/build failure (exit 1) | proof accepted (exit 0) |
| L2 | harness/build failure (exit 1) | proof accepted (exit 0) |
| L3 | harness/build failure (exit 1) | proof accepted (exit 0) |
| CTRL-ARITH | harness/build failure (exit 1) | proof_failed (exit 1) |
| CTRL-LIST | harness/build failure (exit 1) | proof_failed (exit 1) |
| CTRL-NAT-WITNESS | harness/build failure (exit 1) | proof accepted (exit 0) |
| CTRL-LIST-WITNESS | harness/build failure (exit 1) | proof accepted (exit 0) |

All 12 isolated module-path runs exited 1 before elaborating a target. The eight predeclared propositions and two non-vacuity witnesses exited 0 with empty diagnostics in the measured rerun. The two invalid controls exited 1 with tactic errors. No run reported resource exhaustion or a timeout. Coverage is **8/8 predeclared propositions**; controls are excluded.

## Per-case complete generated source and Lean diagnostics

Commands ran from `lean/`. For each ID below, the complete generated source was saved at `.lake/math002_harness/<ID>.lean`. The setup reproduction used `env LEAN_PATH=.lake/math002_harness/empty lean .lake/math002_harness/<ID>.lean`; the measured rerun used `lake env lean .lake/math002_harness/<ID>.lean`. The empty path directory had no `Colony` module. Output is combined standard output and standard error. The sole output normalization replaces the absolute Lean toolchain library path on the final line of each setup diagnostic with `<LEAN_TOOLCHAIN_LIB>` using `re.sub(r'(?m)^/[^\n]*leanprover--lean4---v4\.35\.0/lib/lean$', '<LEAN_TOOLCHAIN_LIB>', output)`. All other characters, including emitted relative source paths and line/column numbers, are unchanged. The measured control diagnostics have no normalization.

### A1

Complete generated source:

```lean
import Colony.Tactic

theorem math002_A1 (n : Nat) : n + 0 = n := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/A1.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### A2

Complete generated source:

```lean
import Colony.Tactic

theorem math002_A2 (n : Nat) : 0 + n = n := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/A2.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### A3

Complete generated source:

```lean
import Colony.Tactic

theorem math002_A3 (x y : Nat) : x + y = y + x := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/A3.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### A4

Complete generated source:

```lean
import Colony.Tactic

theorem math002_A4 (x y z : Nat) : (x + y) + z = x + (y + z) := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/A4.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### O1

Complete generated source:

```lean
import Colony.Tactic

theorem math002_O1 (x y z : Nat) : x ≤ y → x + z ≤ y + z := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/O1.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### L1

Complete generated source:

```lean
import Colony.Tactic

theorem math002_L1 (xs ys : List Nat) : (xs ++ ys).length = xs.length + ys.length := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/L1.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### L2

Complete generated source:

```lean
import Colony.Tactic

theorem math002_L2 (xs : List Nat) : xs.reverse.length = xs.length := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/L2.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### L3

Complete generated source:

```lean
import Colony.Tactic

theorem math002_L3 (xs : List Nat) : xs.reverse.reverse = xs := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/L3.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### CTRL-ARITH

Complete generated source:

```lean
import Colony.Tactic

theorem math002_invalid_arith (n : Nat) : n + 1 = n := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/CTRL-ARITH.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof_failed`, exit 1; full diagnostic:

```text
.lake/math002_harness/CTRL-ARITH.lean:3:58: error: colony: the initial proof portfolio could not close this goal
```

### CTRL-LIST

Complete generated source:

```lean
import Colony.Tactic

theorem math002_invalid_list (xs : List Nat) : xs.length = 0 := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/CTRL-LIST.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof_failed`, exit 1; full diagnostic:

```text
.lake/math002_harness/CTRL-LIST.lean:3:67: error: colony: the initial proof portfolio could not close this goal
```

### CTRL-NAT-WITNESS

Complete generated source:

```lean
import Colony.Tactic

theorem math002_witness_nat : 1 + 1 = 2 := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/CTRL-NAT-WITNESS.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

### CTRL-LIST-WITNESS

Complete generated source:

```lean
import Colony.Tactic

theorem math002_witness_list : ([0] : List Nat).length = 1 := by colony
```

Isolated module-path run — `harness/build failure`, exit 1; full diagnostic with the single path normalization stated above:

```text
.lake/math002_harness/CTRL-LIST-WITNESS.lean:1:0: error: unknown module prefix 'Colony'

No directory 'Colony' or file 'Colony.olean' in the search path entries:
.lake/math002_harness/empty
<LEAN_TOOLCHAIN_LIB>
```

Measured Lake run — `proof accepted`, exit 0; empty diagnostic output.

## Control data and axiom dependencies

- Invalid arithmetic: `n = 0` makes `n + 1 = n` become `1 = 0`.
- Invalid list: `xs = [0]` makes `xs.length = 0` become `1 = 0`.
- Non-vacuity witnesses: `1 + 1 = 2` and `([0] : List Nat).length = 1` were each accepted with exactly `by colony`, as shown above.

After importing `Colony.Examples.FoundationsCoverage`, `#print axioms` reported:

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

No `sorry`, `admit`, or custom axiom was introduced.

## Reproduction record and assurance

- Starting reviewed revision and unchanged tactic implementation: `929ec986830a8ed0d31c2b73cb737334fc86c47d`. The current reviewed MATH002 commit is `0d67bc91e539a5a5fdd6ebe17b1eed2ef5a4c49e`; `lean/Colony/Tactic.lean` has no diff from the starting revision.
- Toolchain: `lean/lean-toolchain` contains `leanprover/lean4:v4.35.0`.
- Original setup sequence reported in the first run: `lake env lean <generated-source>` before `lake build Colony.Tactic`, then `lake build Colony.Tactic` and measured reruns. Full original prebuild diagnostics were not retained, as noted above.
- Evidence rerun commands: the per-case isolated and measured invocations specified above. The per-case full sources and outputs are recorded in this report.
- Build check: `lake build` exited 0, `Build completed successfully (16 jobs)`; it replayed existing unrelated linter warnings.
- Axiom check: `printf` supplied `import Colony.Examples.FoundationsCoverage` and eight `#print axioms` commands to `lake env lean --stdin`; exit 0, output above.
- This reports elaborator/kernel acceptance in the pinned local Lean build. It does not establish exported replay, independent-kernel acceptance, correspondence to Cardano execution, or a new official benchmark score.
