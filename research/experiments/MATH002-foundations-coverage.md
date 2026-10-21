# MATH002: foundational mathematics single-call coverage

Latest clean measurement: **8/8 fixed targets accepted**, both invalid controls rejected and both true witnesses accepted. Complete fresh source/diagnostic capture appears under “Clean predeclared measurement: review remediation”. Historical missing diagnostics remain an evidence gap. The candidate under review is `b5e6fd1111ae6c02dde39d839ea10005aacea564`; this report remediation is an uncommitted working-tree update on that candidate.

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

## Historical outcome and evidence status

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

- Starting reviewed revision and unchanged tactic implementation: `929ec986830a8ed0d31c2b73cb737334fc86c47d`. The supplied candidate containing this historical evidence is `b5e6fd1111ae6c02dde39d839ea10005aacea564` (the prior reference to `0d67bc91e539a5a5fdd6ebe17b1eed2ef5a4c49e` incorrectly identified the candidate); `lean/Colony/Tactic.lean` has no diff from the starting revision.
- Toolchain: `lean/lean-toolchain` contains `leanprover/lean4:v4.35.0`.
- Original setup sequence reported in the first run: `lake env lean <generated-source>` before `lake build Colony.Tactic`, then `lake build Colony.Tactic` and measured reruns. Full original prebuild diagnostics were not retained, as noted above.
- Evidence rerun commands: the per-case isolated and measured invocations specified above. The per-case full sources and outputs are recorded in this report.
- Build check: `lake build` exited 0, `Build completed successfully (16 jobs)`; it replayed existing unrelated linter warnings.
- Axiom check: `printf` supplied `import Colony.Examples.FoundationsCoverage` and eight `#print axioms` commands to `lake env lean --stdin`; exit 0, output above.
- This reports elaborator/kernel acceptance in the pinned local Lean build. It does not establish exported replay, independent-kernel acceptance, correspondence to Cardano execution, or a new official benchmark score.


## Clean predeclared measurement: review remediation

This is one new bounded measurement, independent of MATH001, on the working tree based on candidate `b5e6fd1111ae6c02dde39d839ea10005aacea564`. The reviewed tactic base remains `929ec986830a8ed0d31c2b73cb737334fc86c47d`. Before invoking Lean, `git diff 929ec986830a8ed0d31c2b73cb737334fc86c47d -- lean/Colony/Tactic.lean lean/Colony/Procedures lean/lean-toolchain lean/lakefile.toml lean/lake-manifest.json` produced empty output (exit 0). The tactic Git blob at both revisions is `18ba79ae646af8f2a50726ef95abe808fcd97a68`.

Scope and acceptance fixed before this run: remeasure exactly A1–A4, O1, L1–L3 from the matrix above, preserving all original statements, binder spellings, assumptions and bounds. Retain the two invalid controls and two non-vacuity witnesses above, excluded from coverage. Binder names are local parameters introduced in each standalone theorem; no prior example/helper theorem is imported. No replacement target, helper proof, retry, tactic change, or score/corpus/toolchain change is permitted. All generated sources will be written and embedded below before the first Lean invocation. Every invocation, including setup/build failures, will retain complete output and exit status from its first execution. Successful targets must also emit their actual axiom dependencies. Independent subprocesses are the failure-check harness: invalid declarations never enter the imported coverage module; an invalid control passes its sanity check only with `proof_failed` plus an accepted true witness.

Bounds: external timeout 30 seconds for each case and axiom inspection; 120 seconds for builds. No Lean heartbeat or recursion option is changed, so pinned-toolchain defaults apply. `resource_exhaustion` includes an external timeout, heartbeat/recursion exhaustion, or out-of-memory diagnostic. `proof_failed` requires the actual colony goal-closing error; other nonzero setup/compiler results are `harness/build_failure`. No category counts as positive coverage without acceptance and axiom evidence. Capture uses combined stdout/stderr without truncation or normalization. No artificial empty-LEAN_PATH run is part of this measurement.

The twelve lost historical setup diagnostics remain an **unrecoverable historical evidence gap**. Neither the old reproduction runs nor this clean run supplies those original bytes. Historical results above are retained for provenance; the clean run below is a distinct observation with capture enabled from its first Lean invocation.

Reproduction: from the repository root, materialize the following harness verbatim as `lean/.lake/math002_clean_capture/run.py` and execute `python3 lean/.lake/math002_clean_capture/run.py` in a fresh ignored capture directory. The harness refuses to overwrite an existing start marker. Sources, outputs and metadata in that directory are transient build artifacts; their complete case source/output evidence is embedded in this report. This report update is uncommitted on the specified candidate; there is no new committed evidence revision yet. A controller must record its eventual publication revision. No worker commit, push, or PR was made.

```python
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path.cwd()
WORK = ROOT / 'lean/.lake/math002_clean_capture'
REPORT = ROOT / 'research/experiments/MATH002-foundations-coverage.md'
CASES = [
    ('A1', 'target', 'math002_A1 (n : Nat) : n + 0 = n'),
    ('A2', 'target', 'math002_A2 (n : Nat) : 0 + n = n'),
    ('A3', 'target', 'math002_A3 (x y : Nat) : x + y = y + x'),
    ('A4', 'target', 'math002_A4 (x y z : Nat) : (x + y) + z = x + (y + z)'),
    ('O1', 'target', 'math002_O1 (x y z : Nat) : x ≤ y → x + z ≤ y + z'),
    ('L1', 'target', 'math002_L1 (xs ys : List Nat) : (xs ++ ys).length = xs.length + ys.length'),
    ('L2', 'target', 'math002_L2 (xs : List Nat) : xs.reverse.length = xs.length'),
    ('L3', 'target', 'math002_L3 (xs : List Nat) : xs.reverse.reverse = xs'),
    ('CTRL-ARITH', 'invalid', 'math002_invalid_arith (n : Nat) : n + 1 = n'),
    ('CTRL-LIST', 'invalid', 'math002_invalid_list (xs : List Nat) : xs.length = 0'),
    ('CTRL-NAT-WITNESS', 'witness', 'math002_witness_nat : 1 + 1 = 2'),
    ('CTRL-LIST-WITNESS', 'witness', 'math002_witness_list : ([0] : List Nat).length = 1'),
]

def append(value):
    with REPORT.open('a') as stream:
        stream.write(value)
        stream.flush()

def digest(data):
    return hashlib.sha256(data).hexdigest()

# Refuse to silently mix a second invocation into the same evidence set.
marker = WORK / 'started.json'
with marker.open('x') as stream:
    json.dump({'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}, stream)

# Generate and persist ALL complete sources before invoking Lean even for setup.
sources = {}
for case_id, kind, declaration in CASES:
    source = 'import Colony.Tactic\n\ntheorem ' + declaration + ' := by colony\n'
    if kind != 'invalid':
        source += '\n#print axioms ' + declaration.split()[0] + '\n'
    sources[case_id] = source
    (WORK / (case_id + '.lean')).write_text(source)
axiom_source = 'import Colony.Examples.FoundationsCoverage\n\n' + ''.join(
    '#print axioms ' + declaration.split()[0] + '\n'
    for _, kind, declaration in CASES if kind == 'target')
(WORK / 'ImportedAxioms.lean').write_text(axiom_source)
append('\n### Clean-run frozen source manifest (before the first Lean invocation)\n\n'
       'Each file below is evaluated in a separate Lean process. No target, witness, or invalid '
       'control imports another case. The only proof body is exactly `by colony`. '
       '`#print axioms` is a diagnostic command outside the proof body. '
       'The invalid sources deliberately omit axiom printing because failed declarations are not proofs.\n')
for case_id, kind, _ in CASES:
    source = sources[case_id]
    append('\n#### Frozen ' + case_id + ' (' + kind + ')\n\n'
           'Source SHA-256: `' + digest(source.encode()) + '`.\n\n```lean\n' + source + '```\n')
append('\n#### Frozen imported-module axiom inspection\n\n```lean\n' + axiom_source + '```\n')

results = []
def capture(label, argv, cwd, timeout, source_id=None):
    append('\n#### Invocation ' + label + '\n\nWorking directory: `' +
           str(cwd.relative_to(ROOT) or '.') + '`. Command: `' + ' '.join(argv) +
           '`. External timeout: ' + str(timeout) + ' seconds.\n')
    try:
        result = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        output, code, timed_out = result.stdout, result.returncode, False
    except subprocess.TimeoutExpired as error:
        output, code, timed_out = error.stdout or b'', None, True
    except OSError as error:
        output, code, timed_out = str(error).encode(), None, False
    # Persist complete untruncated bytes first, then embed them in the durable report.
    (WORK / (label + '.stdout')).write_bytes(output)
    decoded = output.decode('utf-8')
    assert str(ROOT) not in decoded, 'Unexpected machine-local path: retain raw bytes; redact explicitly before publishing'
    if timed_out or re.search(r'maximum number of heartbeats|maximum recursion depth|out of memory', decoded, re.I):
        outcome = 'resource_exhaustion'
    elif code == 0:
        outcome = 'proof_accepted' if source_id else 'check_passed'
    elif source_id and 'colony: the initial proof portfolio could not close this goal' in decoded and 'unknown module' not in decoded:
        outcome = 'proof_failed'
    else:
        outcome = 'harness/build_failure'
    record = {'id': label, 'returncode': code, 'outcome': outcome,
              'output_sha256': digest(output), 'timed_out': timed_out}
    results.append(record)
    (WORK / (label + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    append('\nOutcome: `' + outcome + '`; exit code: `' + str(code) + '`; combined stdout/stderr SHA-256: `' + digest(output) + '`.\n\n')
    append('Complete combined stdout/stderr (no normalization):\n\n```text\n' + decoded + ('\n' if decoded and not decoded.endswith('\n') else '') + '```\n' if decoded else 'Combined stdout/stderr: empty (zero bytes).\n')
    print(label + ': ' + outcome + ' (exit ' + str(code) + ')', flush=True)
    return record

lean = ROOT / 'lean'
capture('toolchain-version', ['lake', 'env', 'lean', '--version'], lean, 30)
built = capture('build-tactic', ['lake', 'build', 'Colony.Tactic'], lean, 120)
if built['returncode'] != 0:
    append('\nSetup failed; no coverage score is assigned and no target attempt is retried.\n')
    raise SystemExit(1)
for case_id, kind, declaration in CASES:
    capture(case_id, ['lake', 'env', 'lean', '.lake/math002_clean_capture/' + case_id + '.lean'], lean, 30, case_id)
capture('build-coverage', ['lake', 'build', 'Colony.Examples.FoundationsCoverage'], lean, 120)
capture('imported-axioms', ['lake', 'env', 'lean', '.lake/math002_clean_capture/ImportedAxioms.lean'], lean, 30)
capture('build-all', ['lake', 'build'], lean, 120)
append('\n### Clean-run outcome table\n\n| ID | Kind | Outcome | Exit |\n|---|---|---|---|\n')
by_id = {row['id']: row for row in results}
for case_id, kind, _ in CASES:
    row = by_id[case_id]
    append('| ' + case_id + ' | ' + kind + ' | ' + row['outcome'] + ' | ' + str(row['returncode']) + ' |\n')
(WORK / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
```

### Clean-run frozen source manifest (before the first Lean invocation)

Each file below is evaluated in a separate Lean process. No target, witness, or invalid control imports another case. The only proof body is exactly `by colony`. `#print axioms` is a diagnostic command outside the proof body. The invalid sources deliberately omit axiom printing because failed declarations are not proofs.

#### Frozen A1 (target)

Source SHA-256: `808468c19d440b3e4f8df658d64bd5243f29f1cda628ee660e3df8137883c9a7`.

```lean
import Colony.Tactic

theorem math002_A1 (n : Nat) : n + 0 = n := by colony

#print axioms math002_A1
```

#### Frozen A2 (target)

Source SHA-256: `992744c5b75fcacc423213c2e81a2eb6e15b9bf6df2755f932113e509dfe34a9`.

```lean
import Colony.Tactic

theorem math002_A2 (n : Nat) : 0 + n = n := by colony

#print axioms math002_A2
```

#### Frozen A3 (target)

Source SHA-256: `4456c62f403e708fff798ce99b7a526898e4dca548910b57e90fa21514b8806d`.

```lean
import Colony.Tactic

theorem math002_A3 (x y : Nat) : x + y = y + x := by colony

#print axioms math002_A3
```

#### Frozen A4 (target)

Source SHA-256: `ca4fb25c0bf7224c62a9583a80bb08c58b28bfb3d57a50201f6864f84f0f5808`.

```lean
import Colony.Tactic

theorem math002_A4 (x y z : Nat) : (x + y) + z = x + (y + z) := by colony

#print axioms math002_A4
```

#### Frozen O1 (target)

Source SHA-256: `1fc61d54d75a6a6fd79f04cddd758a7baa4c4c7b0a92a135b90e05099ef111de`.

```lean
import Colony.Tactic

theorem math002_O1 (x y z : Nat) : x ≤ y → x + z ≤ y + z := by colony

#print axioms math002_O1
```

#### Frozen L1 (target)

Source SHA-256: `f87645bf0c4c920b3175b18fcb9d6629bb1a185194cf582162828d70f1c58a9d`.

```lean
import Colony.Tactic

theorem math002_L1 (xs ys : List Nat) : (xs ++ ys).length = xs.length + ys.length := by colony

#print axioms math002_L1
```

#### Frozen L2 (target)

Source SHA-256: `51971199992d4a4abb7751a4159b3666322e470385faae7858a1f8bf46a719a1`.

```lean
import Colony.Tactic

theorem math002_L2 (xs : List Nat) : xs.reverse.length = xs.length := by colony

#print axioms math002_L2
```

#### Frozen L3 (target)

Source SHA-256: `8bb35a7e95a018b3b6f24eda3c9d0c7a5d25ae9a5253b4398ec71db2b19494a0`.

```lean
import Colony.Tactic

theorem math002_L3 (xs : List Nat) : xs.reverse.reverse = xs := by colony

#print axioms math002_L3
```

#### Frozen CTRL-ARITH (invalid)

Source SHA-256: `c454d460553907fd55c7dc07954f536e6f6651f92c4d79b27f77234aee2858a7`.

```lean
import Colony.Tactic

theorem math002_invalid_arith (n : Nat) : n + 1 = n := by colony
```

#### Frozen CTRL-LIST (invalid)

Source SHA-256: `3d6df093e54e5766629efc9b276e70844958474430cbebd999644cf0bff61a1f`.

```lean
import Colony.Tactic

theorem math002_invalid_list (xs : List Nat) : xs.length = 0 := by colony
```

#### Frozen CTRL-NAT-WITNESS (witness)

Source SHA-256: `2eddf85bae9f9e9cf6bd4b985206d7d15130ad5920da2567af4011911156acb6`.

```lean
import Colony.Tactic

theorem math002_witness_nat : 1 + 1 = 2 := by colony

#print axioms math002_witness_nat
```

#### Frozen CTRL-LIST-WITNESS (witness)

Source SHA-256: `bcf4788d248181d611ac1a87d3643f1b19c32a622788dc8e8982c652799aa4d4`.

```lean
import Colony.Tactic

theorem math002_witness_list : ([0] : List Nat).length = 1 := by colony

#print axioms math002_witness_list
```

#### Frozen imported-module axiom inspection

```lean
import Colony.Examples.FoundationsCoverage

#print axioms math002_A1
#print axioms math002_A2
#print axioms math002_A3
#print axioms math002_A4
#print axioms math002_O1
#print axioms math002_L1
#print axioms math002_L2
#print axioms math002_L3
```

#### Invocation toolchain-version

Working directory: `lean`. Command: `lake env lean --version`. External timeout: 30 seconds.

Outcome: `check_passed`; exit code: `0`; combined stdout/stderr SHA-256: `469679dd8c6cec218a7a5e9a36c7a27decc968dacfe057ab3083f0ef43600dac`.

Complete combined stdout/stderr (no normalization):

```text
Lean (version 4.35.0, arm64-apple-darwin24.6.0, commit eb6cafb7290e8bd5f2937522d8d804f58f02bafc, Release)
```

#### Invocation build-tactic

Working directory: `lean`. Command: `lake build Colony.Tactic`. External timeout: 120 seconds.

Outcome: `check_passed`; exit code: `0`; combined stdout/stderr SHA-256: `31da234bfb532d5d412798fc13e5b1d95ac91fa58156c6feb697b60d6a371c19`.

Complete combined stdout/stderr (no normalization):

```text
Build completed successfully (3 jobs).
```

#### Invocation A1

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/A1.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `22676eee50bbe6084f2dc54d96019ee0739aaa83b9a32c1b7f83c7f013572997`.

Complete combined stdout/stderr (no normalization):

```text
'math002_A1' depends on axioms: [propext, Quot.sound]
```

#### Invocation A2

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/A2.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `237b5ac53a9894de1157ef87cb60d7fb11b3d77c9c86f71ce789778b217a26af`.

Complete combined stdout/stderr (no normalization):

```text
'math002_A2' depends on axioms: [propext, Quot.sound]
```

#### Invocation A3

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/A3.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `1c8333c9670ab2c2768839332ee4c21d1b3ee4ae9b2c4228cc72e6185cdeeb92`.

Complete combined stdout/stderr (no normalization):

```text
'math002_A3' depends on axioms: [propext, Quot.sound]
```

#### Invocation A4

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/A4.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `76ef1830efa6f4653cd3af351fbe1aa93e96383e9d36cf46e93af75300480c7f`.

Complete combined stdout/stderr (no normalization):

```text
'math002_A4' depends on axioms: [propext, Quot.sound]
```

#### Invocation O1

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/O1.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `3d49cb4616b74b441161355035628cc4e6e39e481352deadde1dfad7d3c63450`.

Complete combined stdout/stderr (no normalization):

```text
'math002_O1' depends on axioms: [propext, Quot.sound]
```

#### Invocation L1

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/L1.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `8801a6feebfa64b45a326f4d84346fdc7ec9f9aeeb187565428ec6319ed9ab93`.

Complete combined stdout/stderr (no normalization):

```text
'math002_L1' depends on axioms: [propext]
```

#### Invocation L2

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/L2.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `c84aba81493679ff119b686d0a82d9d0cce94022959617cbee15c3b2b9081bfa`.

Complete combined stdout/stderr (no normalization):

```text
'math002_L2' depends on axioms: [propext]
```

#### Invocation L3

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/L3.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `31246f043d80b49c0e0115a2f848b224914abaaf0c4bfcf0bb6417fc4479ae4f`.

Complete combined stdout/stderr (no normalization):

```text
'math002_L3' depends on axioms: [propext]
```

#### Invocation CTRL-ARITH

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/CTRL-ARITH.lean`. External timeout: 30 seconds.

Outcome: `proof_failed`; exit code: `1`; combined stdout/stderr SHA-256: `1388151c0bf3be59a9365e561842e99102d2c5e19d05d1093fa9df67db9b391b`.

Complete combined stdout/stderr (no normalization):

```text
.lake/math002_clean_capture/CTRL-ARITH.lean:3:58: error: colony: the initial proof portfolio could not close this goal
```

#### Invocation CTRL-LIST

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/CTRL-LIST.lean`. External timeout: 30 seconds.

Outcome: `proof_failed`; exit code: `1`; combined stdout/stderr SHA-256: `ea4ad69b188003b1ac21beb236b8eb3f0d3a18eb5d4ece4003ab3e3399a6c2e2`.

Complete combined stdout/stderr (no normalization):

```text
.lake/math002_clean_capture/CTRL-LIST.lean:3:67: error: colony: the initial proof portfolio could not close this goal
```

#### Invocation CTRL-NAT-WITNESS

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/CTRL-NAT-WITNESS.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `e4d7b38724d4d4571cccbde172e3d5740a4a769ec9fe5d127dbac6a951e51474`.

Complete combined stdout/stderr (no normalization):

```text
'math002_witness_nat' depends on axioms: [propext, Quot.sound]
```

#### Invocation CTRL-LIST-WITNESS

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/CTRL-LIST-WITNESS.lean`. External timeout: 30 seconds.

Outcome: `proof_accepted`; exit code: `0`; combined stdout/stderr SHA-256: `a1e0e5906e3b22ee1cc642f2621e0a388abe11b6bb7787c18657150a08bee97f`.

Complete combined stdout/stderr (no normalization):

```text
'math002_witness_list' depends on axioms: [propext]
```

#### Invocation build-coverage

Working directory: `lean`. Command: `lake build Colony.Examples.FoundationsCoverage`. External timeout: 120 seconds.

Outcome: `check_passed`; exit code: `0`; combined stdout/stderr SHA-256: `aee3d70d3b2c9bacc17719f0f81462902128b1735583320360093bc2f7ae9f37`.

Complete combined stdout/stderr (no normalization):

```text
Build completed successfully (4 jobs).
```

#### Invocation imported-axioms

Working directory: `lean`. Command: `lake env lean .lake/math002_clean_capture/ImportedAxioms.lean`. External timeout: 30 seconds.

Outcome: `check_passed`; exit code: `0`; combined stdout/stderr SHA-256: `57ed9dd393e95bef1df7adb99fd0ffc6da39ff2d7a2a267d40a25fa5c925fb68`.

Complete combined stdout/stderr (no normalization):

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

#### Invocation build-all

Working directory: `lean`. Command: `lake build`. External timeout: 120 seconds.

Outcome: `check_passed`; exit code: `0`; combined stdout/stderr SHA-256: `78d4142d3a437448b416dce0704f62b5994339c6f0517b8331672642cabbd9b4`.

Complete combined stdout/stderr (no normalization):

```text
⚠ [6/16] Replayed Colony.Examples.OptionBranching
warning: Colony/Examples/OptionBranching.lean:13:5: Variable name `irrelevant` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _irrelevant

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/OptionBranching.lean:19:9: Variable name `choice` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _choice

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [7/16] Replayed Colony.Examples.ResultFlow
warning: Colony/Examples/ResultFlow.lean:41:39: Variable name `irrelevant` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _irrelevant

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ResultFlow.lean:53:9: Variable name `result` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _result

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ResultFlow.lean:77:9: Variable name `state` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _state

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ResultFlow.lean:77:29: Variable name `result` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _result

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [8/16] Replayed Colony.Examples.ListStateInvariant
warning: Colony/Examples/ListStateInvariant.lean:35:9: Variable name `state` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _state

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ListStateInvariant.lean:35:29: Variable name `command` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _command

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [9/16] Replayed Colony.Examples.AccumulatorLength
warning: Colony/Examples/AccumulatorLength.lean:18:6: `simp` already closes the goal

Hint: Use `simp` instead of `simpa`:
  [apply] simp [copyInto, ih, Nat.add_assoc, Nat.add_comm, Nat.add_left_comm]

Note: This linter can be disabled with `set_option linter.unnecessarySimpa false`
warning: Colony/Examples/AccumulatorLength.lean:20:9: Variable name `xs` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _xs

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/AccumulatorLength.lean:20:12: Variable name `acc` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _acc

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [10/16] Replayed Colony.Examples.FuelStateInvariant
warning: Colony/Examples/FuelStateInvariant.lean:33:9: Variable name `fuel` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _fuel

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/FuelStateInvariant.lean:34:5: Variable name `h` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [11/16] Replayed Colony.Examples.KeyedStateInvariant
warning: Colony/Examples/KeyedStateInvariant.lean:44:9: Variable name `state` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _state

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/KeyedStateInvariant.lean:44:25: Variable name `key` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _key

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/KeyedStateInvariant.lean:44:29: Variable name `value` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _value

Note: This linter can be disabled with `set_option linter.unusedVariables false`
ℹ [15/16] Replayed SeedProofs
info: SeedProofs.lean:6:0: 'case_arithmetic_monotonicity' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:10:0: 'case_reverse_accumulator_length' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:14:0: 'case_count_accumulator_invariant' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:18:0: 'case_recursive_program_nonvacuity' depends on axioms: [propext]
info: SeedProofs.lean:22:0: 'case_account_state_invariant' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:26:0: 'case_allocated_payments_cover_sales' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:30:0: 'case_allocated_payments_nonvacuity' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:34:0: 'case_shared_payment_attack_witness' depends on axioms: [propext, Quot.sound]
Build completed successfully (16 jobs).
```

### Clean-run outcome table

| ID | Kind | Outcome | Exit |
|---|---|---|---|
| A1 | target | proof_accepted | 0 |
| A2 | target | proof_accepted | 0 |
| A3 | target | proof_accepted | 0 |
| A4 | target | proof_accepted | 0 |
| O1 | target | proof_accepted | 0 |
| L1 | target | proof_accepted | 0 |
| L2 | target | proof_accepted | 0 |
| L3 | target | proof_accepted | 0 |
| CTRL-ARITH | invalid | proof_failed | 1 |
| CTRL-LIST | invalid | proof_failed | 1 |
| CTRL-NAT-WITNESS | witness | proof_accepted | 0 |
| CTRL-LIST-WITNESS | witness | proof_accepted | 0 |


### Clean-run result and assurance

Coverage is **8/8** predeclared propositions. Both intentionally invalid claims returned `proof_failed`; their concrete counterexample inputs remain `n = 0` and `xs = [0]`, respectively, each reducing the claim to `1 = 0`. Both true non-vacuity witnesses were accepted. All four controls are excluded from coverage. None of the 17 clean-run Lean invocations timed out or reported resource exhaustion or a harness/build failure. The two invalid claims are the only proof failures; the complete actual diagnostics and source bytes are embedded above, and no failed target was repaired or substituted.

The ten accepted proof attempts all have exactly `by colony` as the entire proof body. A1–A4, O1 and the arithmetic witness depend on `[propext, Quot.sound]`; L1–L3 and the list witness depend on `[propext]`. No accepted proof reports a native evaluation axiom, recovery placeholder, or custom axiom. The imported module's eight declarations exactly match the standalone successful target declarations, and its eight axiom reports agree. The module imports only `Colony.Tactic`; the standalone trials import only that module as well. No other example/helper proofs supply these targets.

Both `lake build Colony.Examples.FoundationsCoverage` and `lake build` returned 0. Lake reused local build artifacts and replayed existing unrelated linter warnings; the 12 standalone trials freshly elaborated their supplied sources. Assurance is **local Lean elaborator/kernel acceptance with the displayed standard axiom dependencies**. There is no independent kernel replay, exported proof replay, Cardano execution correspondence, performance comparison, or new official benchmark score.

The following post-run evidence check was executed before and after final report assembly, without invoking Lean or retrying any case. Command from repository root: `python3 lean/.lake/math002_clean_capture/verify.py`; both invocations exited 0 with the identical output below. Complete verification source:

```python
from pathlib import Path
import hashlib
import json
import re

work = Path('lean/.lake/math002_clean_capture')
report = Path('research/experiments/MATH002-foundations-coverage.md').read_text()
rows = json.loads((work / 'results.json').read_text())
assert len(rows) == 17
by_id = {row['id']: row for row in rows}
targets = ['A1', 'A2', 'A3', 'A4', 'O1', 'L1', 'L2', 'L3']
witnesses = ['CTRL-NAT-WITNESS', 'CTRL-LIST-WITNESS']
invalids = ['CTRL-ARITH', 'CTRL-LIST']
for row in rows:
    raw = (work / (row['id'] + '.stdout')).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['output_sha256']
    assert raw.decode() in report
    assert not row['timed_out']
for case_id in targets + witnesses:
    assert by_id[case_id]['outcome'] == 'proof_accepted'
    assert by_id[case_id]['returncode'] == 0
    source = (work / (case_id + '.lean')).read_text()
    assert source in report
    assert re.findall(r'^import (.+)$', source, re.M) == ['Colony.Tactic']
    assert len(re.findall(r':= by colony$', source, re.M)) == 1
    output = (work / (case_id + '.stdout')).read_text()
    dependencies = re.findall(r"depends on axioms: \[([^\]]*)\]", output)
    assert len(dependencies) == 1
    assert set(dependencies[0].split(', ')) <= {'propext', 'Quot.sound', 'Classical.choice'}
for case_id in invalids:
    assert by_id[case_id]['outcome'] == 'proof_failed'
    assert by_id[case_id]['returncode'] == 1
    assert (work / (case_id + '.lean')).read_text() in report
for row in rows:
    if row['id'] not in targets + witnesses + invalids:
        assert row['outcome'] == 'check_passed' and row['returncode'] == 0
module = Path('lean/Colony/Examples/FoundationsCoverage.lean').read_text()
assert re.findall(r'^import (.+)$', module, re.M) == ['Colony.Tactic']
expected = [re.search(r'^theorem .+$', (work / (case_id + '.lean')).read_text(), re.M).group() for case_id in targets]
assert re.findall(r'^theorem .+$', module, re.M) == expected
imported_axioms = (work / 'imported-axioms.stdout').read_text()
for case_id in targets:
    assert (work / (case_id + '.stdout')).read_text().strip() in imported_axioms
assert 'import Colony.Examples.FoundationsCoverage' in Path('lean/Colony.lean').read_text().splitlines()
print('Verified 17/17 captured Lean invocations and all raw output hashes.')
print('Verified coverage 8/8, invalid controls rejected 2/2, true witnesses accepted 2/2.')
print('Verified all 10 accepted proof axiom reports; imported target reports agree.')
print('Verified exact source declarations match the eight imported by-colony proofs.')
```

Complete verification stdout/stderr:

```text
Verified 17/17 captured Lean invocations and all raw output hashes.
Verified coverage 8/8, invalid controls rejected 2/2, true witnesses accepted 2/2.
Verified all 10 accepted proof axiom reports; imported target reports agree.
Verified exact source declarations match the eight imported by-colony proofs.
```


### Ancillary repository checks (excluded from coverage)

`node --check observatory/dist/app.js` ran from repository root: exit 0, empty stdout/stderr.

`python3 -m unittest discover -s tests -v` ran from repository root with a 120-second external timeout. It did not complete within that bound. The Python capture wrapper exited 1; no test-suite return code is available. The actual retained wrapper exception was:

```text
subprocess.TimeoutExpired: Command '['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v']' timed out after 120 seconds
```

The ancillary wrapper did not persist partial unit-test stdout on timeout; that transcript is unavailable. No unit-test pass or individual test outcome is claimed, and the suite was not retried. This ancillary retention limitation is separate from the complete first-invocation capture of every clean-run Lean source and diagnostic above.

The required unchanged evaluator ran from repository root as `python3 scripts/evaluate_lean.py --output lean/.lake/math002_clean_capture/benchmark-results.json`: exit 0. The output location was moved into ignored build storage to avoid modifying a fourth tracked file. This invokes the existing evaluator and its default strategies unchanged; its results are regression observations, excluded from the foundations coverage count. Complete evaluator stdout/stderr follows. The sole normalization replaces the resolved repository prefix in the evaluator's final output-file field with `<REPOSITORY>`; all case diagnostics above have no normalization.

```text
⚠ [6/16] Replayed Colony.Examples.OptionBranching
warning: Colony/Examples/OptionBranching.lean:13:5: Variable name `irrelevant` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _irrelevant

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/OptionBranching.lean:19:9: Variable name `choice` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _choice

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [7/16] Replayed Colony.Examples.ResultFlow
warning: Colony/Examples/ResultFlow.lean:41:39: Variable name `irrelevant` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _irrelevant

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ResultFlow.lean:53:9: Variable name `result` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _result

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ResultFlow.lean:77:9: Variable name `state` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _state

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ResultFlow.lean:77:29: Variable name `result` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _result

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [8/16] Replayed Colony.Examples.ListStateInvariant
warning: Colony/Examples/ListStateInvariant.lean:35:9: Variable name `state` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _state

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/ListStateInvariant.lean:35:29: Variable name `command` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _command

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [9/16] Replayed Colony.Examples.AccumulatorLength
warning: Colony/Examples/AccumulatorLength.lean:18:6: `simp` already closes the goal

Hint: Use `simp` instead of `simpa`:
  [apply] simp [copyInto, ih, Nat.add_assoc, Nat.add_comm, Nat.add_left_comm]

Note: This linter can be disabled with `set_option linter.unnecessarySimpa false`
warning: Colony/Examples/AccumulatorLength.lean:20:9: Variable name `xs` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _xs

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/AccumulatorLength.lean:20:12: Variable name `acc` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _acc

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [10/16] Replayed Colony.Examples.FuelStateInvariant
warning: Colony/Examples/FuelStateInvariant.lean:33:9: Variable name `fuel` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _fuel

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/FuelStateInvariant.lean:34:5: Variable name `h` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h

Note: This linter can be disabled with `set_option linter.unusedVariables false`
⚠ [11/16] Replayed Colony.Examples.KeyedStateInvariant
warning: Colony/Examples/KeyedStateInvariant.lean:44:9: Variable name `state` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _state

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/KeyedStateInvariant.lean:44:25: Variable name `key` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _key

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: Colony/Examples/KeyedStateInvariant.lean:44:29: Variable name `value` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _value

Note: This linter can be disabled with `set_option linter.unusedVariables false`
ℹ [15/16] Replayed SeedProofs
info: SeedProofs.lean:6:0: 'case_arithmetic_monotonicity' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:10:0: 'case_reverse_accumulator_length' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:14:0: 'case_count_accumulator_invariant' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:18:0: 'case_recursive_program_nonvacuity' depends on axioms: [propext]
info: SeedProofs.lean:22:0: 'case_account_state_invariant' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:26:0: 'case_allocated_payments_cover_sales' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:30:0: 'case_allocated_payments_nonvacuity' depends on axioms: [propext, Quot.sound]
info: SeedProofs.lean:34:0: 'case_shared_payment_attack_witness' depends on axioms: [propext, Quot.sound]
Build completed successfully (16 jobs).
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
simp     arithmetic_monotonicity                  certified
simp     reverse_accumulator_length               proof_failed
simp     count_accumulator_invariant              proof_failed
simp     recursive_program_nonvacuity             certified
simp     account_state_invariant                  proof_failed
simp     allocated_payments_cover_sales           proof_failed
simp     allocated_payments_nonvacuity            certified
simp     shared_payment_attack_witness            certified
simp     false_shared_payment_safety              proof_failed
simp     reverse_involution_frontier              proof_failed
omega    arithmetic_monotonicity                  certified
omega    reverse_accumulator_length               proof_failed
omega    count_accumulator_invariant              proof_failed
omega    recursive_program_nonvacuity             proof_failed
omega    account_state_invariant                  proof_failed
omega    allocated_payments_cover_sales           proof_failed
omega    allocated_payments_nonvacuity            proof_failed
omega    shared_payment_attack_witness            proof_failed
omega    false_shared_payment_safety              proof_failed
omega    reverse_involution_frontier              proof_failed
grind    arithmetic_monotonicity                  certified
grind    reverse_accumulator_length               proof_failed
grind    count_accumulator_invariant              proof_failed
grind    recursive_program_nonvacuity             proof_failed
grind    account_state_invariant                  proof_failed
grind    allocated_payments_cover_sales           proof_failed
grind    allocated_payments_nonvacuity            proof_failed
grind    shared_payment_attack_witness            proof_failed
grind    false_shared_payment_safety              proof_failed
grind    reverse_involution_frontier              proof_failed
{
  "output": "<REPOSITORY>/lean/.lake/math002_clean_capture/benchmark-results.json",
  "summary": {
    "colony": {
      "positive_certified": 8,
      "positive_total": 8,
      "negative_checks": [
        {
          "id": "false_shared_payment_safety",
          "rejected": true,
          "positive_witnesses_certified": true,
          "sanity_pass": true
        }
      ],
      "unsupported_certified": 1,
      "timeouts": 0,
      "evidence_errors": 0
    },
    "grind": {
      "positive_certified": 1,
      "positive_total": 8,
      "negative_checks": [
        {
          "id": "false_shared_payment_safety",
          "rejected": true,
          "positive_witnesses_certified": false,
          "sanity_pass": false
        }
      ],
      "unsupported_certified": 0,
      "timeouts": 0,
      "evidence_errors": 0
    },
    "omega": {
      "positive_certified": 1,
      "positive_total": 8,
      "negative_checks": [
        {
          "id": "false_shared_payment_safety",
          "rejected": true,
          "positive_witnesses_certified": false,
          "sanity_pass": false
        }
      ],
      "unsupported_certified": 0,
      "timeouts": 0,
      "evidence_errors": 0
    },
    "simp": {
      "positive_certified": 4,
      "positive_total": 8,
      "negative_checks": [
        {
          "id": "false_shared_payment_safety",
          "rejected": true,
          "positive_witnesses_certified": true,
          "sanity_pass": true
        }
      ],
      "unsupported_certified": 0,
      "timeouts": 0,
      "evidence_errors": 0
    }
  }
}
```

All existing-evaluator per-case outcomes (retained independently of its aggregate summary):

| Case | colony | simp | omega | grind |
|---|---|---|---|---|
| arithmetic_monotonicity | certified | certified | certified | certified |
| reverse_accumulator_length | certified | proof_failed | proof_failed | proof_failed |
| count_accumulator_invariant | certified | proof_failed | proof_failed | proof_failed |
| recursive_program_nonvacuity | certified | certified | proof_failed | proof_failed |
| account_state_invariant | certified | proof_failed | proof_failed | proof_failed |
| allocated_payments_cover_sales | certified | proof_failed | proof_failed | proof_failed |
| allocated_payments_nonvacuity | certified | certified | proof_failed | proof_failed |
| shared_payment_attack_witness | certified | certified | proof_failed | proof_failed |
| false_shared_payment_safety | proof_failed | proof_failed | proof_failed | proof_failed |
| reverse_involution_frontier | certified | proof_failed | proof_failed | proof_failed |

### Final revision and scope record

- Reviewed tactic base: `929ec986830a8ed0d31c2b73cb737334fc86c47d`.
- Supplied evidence candidate HEAD: `b5e6fd1111ae6c02dde39d839ea10005aacea564`. This identifies the revision containing the historical submitted evidence; the clean-run addition is an uncommitted report update based on that exact HEAD, not a claim that HEAD already contains this new text.
- No source changes were needed for this remediation: the coverage module and its import remain exactly as in the supplied candidate. Only this research artifact differs from candidate HEAD. Relative to the reviewed base, the complete candidate plus remediation is limited to the three permitted files. No tactic, procedure, toolchain, corpus, evaluator, score, policy, or existing example changed.
- `git diff --check`: exit 0 before final report assembly; checked again after assembly. The worker did not commit or publish; the eventual controller publication revision remains to be recorded.

Source SHA-256 identifiers for the measured working-tree code (report omitted to avoid a self-referential hash):

| File | SHA-256 |
|---|---|
| `lean/Colony/Tactic.lean` | `4fe8028c60b00c5c8d6bbadf8b9641bafc69aad6197798cbbab042eaba5b5f07` |
| `lean/Colony/Procedures/ListState.lean` | `b27d18d31fb9ca2be92077841edabab5c9863eb2e068dac7afeed5f61c35bfb0` |
| `lean/lean-toolchain` | `ca5f1f601d34c49079e38d7e7041eb0f2a9c227fbc1df0f404820069a052330c` |
| `lean/lakefile.toml` | `bbf3548897b674a979d6a8d529e4944888141b057baa820a378815204b78f77d` |
| `lean/Colony/Examples/FoundationsCoverage.lean` | `ba47060bf6eceaf5bcf9d4bfac3ad48172689291b53a5e517112d6b21e9feef2` |
| `lean/Colony.lean` | `f8d100f592ebc72db9bca1f2b9feba8bfefdfdc731484a06742f0019751a1c27` |
