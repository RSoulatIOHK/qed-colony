# AUTO-3f0db8ced4: bounded commutative arithmetic search

## Scope and source

Probe `nng4.add_comm` and `nng4.add_right_comm` with unchanged scored statements
and tactic-only `by colony` proofs. Record each independently, plus a
noncommutative control and an invalid equality.
`benchmarks/results/blaster-nng4-first-run.json` recorded `proof_failed` for
both `colony` cases before this candidate.

Base revision: `9b091914e32eac614f784c19fb2df9729ce4d9aa`.
**Tested candidate commit: `ed6b935b7aa7043c574cd1e3f85921755f546275`**
(not the base revision). Its `lean/Colony/Tactic.lean` SHA-256 was
`59110dea041530994e6e2d3a254b8dfd0c9b8b2dcdbf0226538a464061f1daf5`.
The working tree was clean before this record was revised. This record edit
does not alter the tactic source.

The candidate adds one `ac_rfl` attempt to the finite arithmetic portfolio
after `omega` and `simp_all <;> omega`. `ac_rfl` uses generic associativity and
commutativity reasoning. The tactic names neither scored theorem nor an
operator-specific lemma. The portfolio makes one attempt per branch and does
not recursively enumerate rewrites. It is a bounded normalization/search
probe, not a general rewrite engine. Existing local hypotheses remain
available to the other portfolio branches.

## Source and build evidence

Commands were run from the repository root unless prefixed with `cd lean &&`.
`lean/lean-toolchain` specifies `leanprover/lean4:v4.35.0`.

```text
$ git rev-parse HEAD
ed6b935b7aa7043c574cd1e3f85921755f546275
$ git show HEAD:lean/Colony/Tactic.lean | sha256sum
59110dea041530994e6e2d3a254b8dfd0c9b8b2dcdbf0226538a464061f1daf5  -
$ sha256sum lean/Colony/Tactic.lean
59110dea041530994e6e2d3a254b8dfd0c9b8b2dcdbf0226538a464061f1daf5  lean/Colony/Tactic.lean
$ cd lean && lake build Colony
Build completed successfully (13 jobs).
```

The build exited 0. It also replayed existing linter warnings in example
modules (`OptionBranching`, `ResultFlow`, `ListStateInvariant`,
`AccumulatorLength`, `FuelStateInvariant`, and `KeyedStateInvariant`).

## Independent scored-goal inputs and captured Lean output

Each block is a separate `lake env lean --stdin` process. In particular,
`add_right_comm` has no newly declared `add_comm` theorem in scope. The
headers, `ℕ` abbreviation, and `set_option maxHeartbeats 200000` match the
frozen NNG4 generated source. The only proof text is `by colony`.

### `nng4.add_comm`

```sh
cd lean && lake env lean --stdin <<'LEAN'
import Colony.Tactic
set_option maxHeartbeats 200000
namespace BlasterBenchmarks.NNG4
abbrev ℕ := Nat
section Addition
open Nat
  theorem add_comm (a b : ℕ) : a + b = b + a := by colony
#print axioms BlasterBenchmarks.NNG4.add_comm
end Addition
end BlasterBenchmarks.NNG4
LEAN
```

Exit code: 0. Complete captured Lean output:

```text
'BlasterBenchmarks.NNG4.add_comm' depends on axioms: [propext, Quot.sound]
```

### `nng4.add_right_comm` in isolation

```sh
cd lean && lake env lean --stdin <<'LEAN'
import Colony.Tactic
set_option maxHeartbeats 200000
namespace BlasterBenchmarks.NNG4
abbrev ℕ := Nat
section Addition
open Nat
  theorem add_right_comm (a b c : ℕ) : a + b + c = a + c + b := by colony
#print axioms BlasterBenchmarks.NNG4.add_right_comm
end Addition
end BlasterBenchmarks.NNG4
LEAN
```

Exit code: 0. Complete captured Lean output:

```text
'BlasterBenchmarks.NNG4.add_right_comm' depends on axioms: [propext, Quot.sound]
```

## Negative controls and captured Lean output

The subtraction statement is not commutative over naturals. Its direct
`by colony` attempt was expected to fail:

```sh
cd lean && lake env lean --stdin <<'LEAN'
import Colony.Tactic
set_option maxHeartbeats 200000
namespace ColonyControl
theorem sub_comm (a b : Nat) : a - b = b - a := by colony
end ColonyControl
LEAN
```

Exit code: 1. Complete captured Lean output:

```text
<stdin>:4:51: error: colony: the initial proof portfolio could not close this goal
```

The intentionally invalid equality was attempted directly:

```sh
cd lean && lake env lean --stdin <<'LEAN'
import Colony.Tactic
set_option maxHeartbeats 200000
namespace ColonyControl
theorem invalid : (0 : Nat) = 1 := by colony
end ColonyControl
LEAN
```

Exit code: 1. Complete captured Lean output:

```text
<stdin>:4:38: error: colony: the initial proof portfolio could not close this goal
```

## Interpretation and failed probe

Lean accepted both positive theorem declarations under the local elaborator
and kernel. Their reported dependencies are `propext` and `Quot.sound`; no
`sorry`, `admit`, added axiom, native evaluation axiom, or disabled kernel check
was used. The negative controls remained unsolved. No exported replay,
independent-kernel check, or Cardano execution correspondence was tested. These
four inputs do not establish broader performance.

An earlier control wrapped the false equality in a negation and introduced its
assumption. `colony` then succeeded by contradiction, so that probe did not
isolate a noncommutative target. It was replaced by the direct subtraction
statement above.
