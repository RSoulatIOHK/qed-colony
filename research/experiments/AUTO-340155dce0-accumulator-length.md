# AUTO-340155dce0: induction for an accumulator length invariant

## Scope and exact example

Added the isolated recursive procedure `Colony.Examples.copyInto`:

```lean
def copyInto (xs acc : List Nat) : List Nat :=
  match xs with
  | [] => acc
  | x :: rest => copyInto rest (x :: acc)
```

The fixed positive theorem statement is:

```lean
theorem copyInto_length (xs acc : List Nat) :
    (copyInto xs acc).length = xs.length + acc.length
```

Its initial `by colony` attempt failed, so the final theorem puts that tactic
attempt under `fail_if_success` and then proves the unchanged statement by
structural induction, generalizing `acc`. A neighboring false target adds one
to the right-hand side and is guarded by `fail_if_success` around `colony`.
No tactic, procedure implementation outside this example, or benchmark policy
was changed.

## Source identity and Lean results

- Base revision: Git `6d4efea988ed6a34038a64bb4c8280290cd15700`.
- Tested candidate source revision: Git
  `96df2af086ed6ff122fda3a22e8b533b6e1e7128`. The build and axiom
  query below were rerun at this revision before this record-only correction.
- `lean/Colony/Examples/AccumulatorLength.lean` SHA-256:
  `554ab22df0c7f032334f071c402b726dcdfe9ba0f016272603efe5944f6068d0`.
- `lean/Colony.lean` SHA-256:
  `5a877f08c84f130f66c09394447150c9d5de28ff6929cdecaf6ae2c0298f99a1`.
- Toolchain: `leanprover/lean4:v4.35.0` (`lean/lean-toolchain`).
- Failed attempt: with the positive theorem body `by colony`, exact command
  `cd lean && lake build Colony`; exit 1. Lean reported
  `error: Colony/Examples/AccumulatorLength.lean:14:2: colony: the initial
  proof portfolio could not close this goal`. The theorem body was then changed
  to retain the same failed tactic attempt under `fail_if_success` and to prove
  the statement by induction.
- Reproduced that failure at the tested candidate source revision without
  modifying the source file. From `lean/`, this command replaces only the
  positive proof body in a stream sent to Lean:

  ```sh
  python3 - <<'PY' | lake env lean --stdin
  from pathlib import Path
  source = Path('Colony/Examples/AccumulatorLength.lean').read_text()
  start = source.index('  fail_if_success colony\n', source.index('theorem copyInto_length'))
  end = source.index('\nexample ', start)
  print(source[:start] + '  colony\n' + source[end:])
  PY
  ```

  It exited 1 with `<stdin>:14:2: error: colony: the initial proof portfolio
  could not close this goal`.
- Final exact build command, from the `lean/` project directory:
  `lake build Colony`; exit 0, `Build completed successfully (9 jobs).`
  Lake replayed the compiled example and its warnings. It also replayed
  existing unused-parameter warnings in `ListStateInvariant`.
- Fresh elaboration command from `lean/`:
  `lake env lean Colony/Examples/AccumulatorLength.lean`; exit 0, with
  unnecessary-`simpa` and unused-parameter warnings in this example.
- Exact axiom query command, from the `lean/` project directory:
  `printf 'import Colony\n#print axioms Colony.Examples.copyInto_length\n' | lake env lean --stdin`;
  exit 0. Output:
  `'Colony.Examples.copyInto_length' depends on axioms: [propext]`.
- `git diff --check`: exit 0.

## Assurance and limits

The final positive theorem is accepted by Lean's elaborator and kernel, with
the reported dependency `[propext]`. The experiment demonstrates that the
existing `colony` tactic failed on this invariant and on the intentionally
false nearby target; the positive theorem's proof after the recorded tactic
failure is an ordinary induction script. Assurance is **elaborator kernel
acceptance only**. No exported replay, independent-kernel acceptance, or
correspondence to Cardano execution is claimed. This is one isolated example,
not a benchmark or performance result.
