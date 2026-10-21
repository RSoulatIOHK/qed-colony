# AUTO-700000bc74: ordered-product monotonicity

## Scope and acceptance

Probe the ordered-goal fallback for `a * t ≤ b * t` from `h : a ≤ b`. The
candidate tactic applies Lean's `Nat.mul_le_mul_right` and closes its premise
with `assumption`. It is independent of the theorem name and benchmark ID.
Acceptance requires the unchanged frozen `BlasterBenchmarks.NNG4.mul_le_mul_right`
declaration to close with exactly `by colony`, a supported reversed control to
close, and unsupported or false ordered goals to remain unsolved.

## Source under test

- Base revision: `9b091914e32eac614f784c19fb2df9729ce4d9aa`.
- Tested candidate HEAD: `960cac94a94e5b391d1f20215baa8b60ac797de1`.
- `shasum -a 256 lean/Colony/Tactic.lean`:
  `8233d4fc0eb3e3d686e483e340a117f49193b41f94440d72a5c134e447137016`.
- Toolchain pin: `leanprover/lean4:v4.35.0`.
- Frozen target: `benchmarks/blaster-nng4-v1.json`, case
  `nng4.mul_le_mul_right`, statement SHA-256
  `867fe0c1710bc59adad0c0a9e6064c1031e55839fa6d1016222a9fbfa571c198`.

## Commands and observed results

Commands ran from the repository root except the four `lake env lean --stdin`
commands, whose working directory was `lean/`. Those probes use standard input,
so no challenge or probe source file was changed.

1. `cd lean && lake build Colony.Tactic` → exit 0,
   `Build completed successfully (3 jobs).`

2. Exact frozen declaration, context, import, body, and axiom report:

   ```sh
   lake env lean --stdin <<'LEAN'
   import Colony.Tactic
   namespace BlasterBenchmarks.NNG4
   abbrev ℕ := Nat
   section AdvMultiplication
   open Nat
     theorem mul_le_mul_right (a b t : ℕ) (h : a ≤ b) : a * t ≤ b * t := by colony
   #print axioms BlasterBenchmarks.NNG4.mul_le_mul_right
   end AdvMultiplication
   end BlasterBenchmarks.NNG4
   LEAN
   ```

   Exit 0, output:

   ```text
   'BlasterBenchmarks.NNG4.mul_le_mul_right' does not depend on any axioms
   ```

3. Same shape with a reversed inequality and a supporting hypothesis:

   ```sh
   lake env lean --stdin <<'LEAN'
   import Colony.Tactic
   namespace OrderedProductControls
   abbrev ℕ := Nat
   section AdvMultiplication
   open Nat
     theorem reversed_with_support (a b t : ℕ) (h : b ≤ a) : b * t ≤ a * t := by colony
   #print axioms OrderedProductControls.reversed_with_support
   end AdvMultiplication
   end OrderedProductControls
   LEAN
   ```

   Exit 0, output:

   ```text
   'OrderedProductControls.reversed_with_support' does not depend on any axioms
   ```

4. Reversed inequality **without** supporting hypothesis:

   ```sh
   lake env lean --stdin <<'LEAN'
   import Colony.Tactic
   namespace OrderedProductControls
   abbrev ℕ := Nat
   section AdvMultiplication
   open Nat
     theorem reversed_without_support (a b t : ℕ) (h : a ≤ b) : b * t ≤ a * t := by colony
   end AdvMultiplication
   end OrderedProductControls
   LEAN
   ```

   Exit 1, output:

   ```text
   <stdin>:6:81: error: colony: the initial proof portfolio could not close this goal
   ```

5. Concrete intentionally false ordered goal:

   ```sh
   lake env lean --stdin <<'LEAN'
   import Colony.Tactic
   namespace OrderedProductControls
   abbrev ℕ := Nat
   section AdvMultiplication
   open Nat
     theorem false_ordered_goal : (2 : ℕ) * 1 ≤ 1 * 1 := by colony
   end AdvMultiplication
   end OrderedProductControls
   LEAN
   ```

   Exit 1, output:

   ```text
   <stdin>:6:57: error: colony: the initial proof portfolio could not close this goal
   ```

6. `node --check observatory/dist/app.js` → exit 0, no output.
   `python3 -m unittest discover -s tests -v` → exit 1:
   `Ran 335 tests in 99.785s`, `FAILED (failures=3, errors=13)`.
   The suite includes passing corpus and benchmark contract tests. Other tests
   encountered denied `ps` execution and local socket binding; additional
   failures occurred in a compiler-audit expectation and pipeline state checks.
   This broad-suite result is not a clean pass.

## Earlier failed probe and assurance

An earlier probe at the base revision used a substitute `ordered_product`
theorem with `import Colony`; it did not check the frozen declaration or the
candidate source. An initial source-file probe outside the Lake package root
also timed out. The standard-input probes above resolve both evidence gaps.

Lean elaborated the two successful `by colony` declarations and its kernel
accepted their proof terms. `#print axioms` reports no axiom dependencies for
either. The tactic uses no `sorry`, `admit`, arbitrary axioms, native evaluation
axioms, or disabled kernel checks. This establishes elaborator/kernel acceptance
for these declarations only; it does not establish exported replay,
independent-kernel acceptance, Cardano execution correspondence, or general
monotonicity for types other than `Nat`.
