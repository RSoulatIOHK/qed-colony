# Measure generic filtering-procedure verification

Task `AUTO-cd69a3c234`; base revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`.

# AUTO-cd69a3c234 — read-only research artifact

**Review result:** The requested diff adds only `research/colony/auto-cd69a3c234.md`. It adds no filtering harness under `lean/Colony/Examples/` and no tactic change. The note says the checkout is at the base revision, but the inspected HEAD was `188db44425be47a7609bd56682c8350bb5c0f984`. Its conclusion that the experiment was unmeasured was accurate for the committed artifact.

The complete added-file content in `git diff 097a4117c7f7038f8d448217d7836a0d95d41bbe..188db44425be47a7609bd56682c8350bb5c0f984` is:

```markdown
# Measure generic filtering-procedure verification

Task `AUTO-cd69a3c234`; base revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`.

## AUTO-cd69a3c234 — generic filtering-procedure verification

**Measured result:** Not completed. This environment mounts the checkout read-only, so I could not add the required research artifact under `research/` or a Lean harness under `lean/Colony/Examples/`. The checkout remains unchanged.

**Inspection:** The checkout is at base revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`. The existing list procedure is `process` over `ListCommand` in `lean/Colony/Procedures/ListState.lean`; it is not a generic filtering procedure. I did not substitute it for the requested experiment or claim a tactic result. `lean/lean-toolchain` specifies Lean 4.35.0, and `cd lean && lake env lean --version` succeeded, reporting Lean 4.35.0. That version check does not verify a filtering theorem.

**Unmeasured:** No unchanged filtering theorem, bounded search configuration, `by colony` attempt, intentionally invalid case, or proof assurance result was established. Therefore there is no exact experiment command or failed proof attempt to report.

The requested artifact and its acceptance criteria remain outstanding; no implementation or tactic change is claimed.
```

`AGENTS.md` requires preserved theorem statements and bounds, non-vacuity and invalid cases, and precise assurance labels. The existing `lean/Colony/Examples/ListStateInvariant.lean` concerns command processing, not filtering. No filtering example exists in that directory.

## Read-only measurement

At HEAD `188db44425be47a7609bd56682c8350bb5c0f984`, I streamed the current `lean/Colony/Procedures/ListState.lean` and `lean/Colony/Tactic.lean` source into Lean 4.35.0, then appended this standalone procedure and **unchanged positive specification**:

```lean
def retain {α : Type} (keep : α → Bool) : List α → List α
  | [] => []
  | x :: xs => if keep x then x :: retain keep xs else retain keep xs

theorem retained_length_bounded {α : Type} (keep : α → Bool) (xs : List α)
    (hbound : xs.length ≤ 3) :
    (retain keep xs).length ≤ 3 := by colony
```

The bound is necessary for the stated conclusion. The configuration is one arbitrary element type, arbitrary Boolean predicate, and input lists of length at most **3**. There is no theorem-name dispatch or benchmark-specific tactic helper.

| Check | Actual result |
| --- | --- |
| Positive theorem with exactly `by colony` | **Failed**, Lean exit 1: `colony: the initial proof portfolio could not close this goal`. |
| Intentionally invalid variant, replacing `≤ 3` with `≤ 2`, with exactly `by colony` | **Failed**, Lean exit 1 with the same diagnostic. |
| Manual proof of the unchanged positive theorem, plus concrete controls | **Accepted**, Lean exit 0. This is **not** a tactic win. |
| Non-vacuity and invalidity witness | Lean accepted that `[0,1,2]` satisfies the input bound, retaining every element returns `[0,1,2]`, and the result’s length is not `≤ 2`. |

The final command, run from `lean/`, was:

```sh
python3 -c '
from pathlib import Path
import subprocess

proc = Path("Colony/Procedures/ListState.lean").read_text()
tactic = Path("Colony/Tactic.lean").read_text()
tactic = "\n".join(line for line in tactic.splitlines()
                   if not line.startswith("import "))
base = "import Lean\nimport Std.Tactic\n" + proc + tactic + """
namespace Colony.Examples.FilterExperiment
def retain {α : Type} (keep : α → Bool) : List α → List α
  | [] => []
  | x :: xs => if keep x then x :: retain keep xs else retain keep xs
"""

cases = {
"positive_by_colony": """
theorem retained_length_bounded {α : Type} (keep : α → Bool) (xs : List α)
    (hbound : xs.length ≤ 3) :
    (retain keep xs).length ≤ 3 := by colony
""",
"invalid_by_colony": """
theorem retained_length_at_most_two {α : Type} (keep : α → Bool) (xs : List α)
    (hbound : xs.length ≤ 3) :
    (retain keep xs).length ≤ 2 := by colony
""",
"manual_and_controls": """
theorem retained_length_bounded {α : Type} (keep : α → Bool) (xs : List α)
    (hbound : xs.length ≤ 3) :
    (retain keep xs).length ≤ 3 := by
  have all : ∀ ys : List α, (retain keep ys).length ≤ ys.length := by
    intro ys
    induction ys with
    | nil => simp [retain]
    | cons x ys ih =>
      by_cases h : keep x = true
      · simp [retain, h]
        omega
      · simp [retain, h]
        omega
  exact Nat.le_trans (all xs) hbound
example : ([0, 1, 2] : List Nat).length ≤ 3 := by decide
example : retain (fun _ : Nat => true) [0, 1, 2] = [0, 1, 2] := by decide
example : ¬ (retain (fun _ : Nat => true) [0, 1, 2]).length ≤ 2 := by decide
#print axioms retained_length_bounded
"""
}
for label, suffix in cases.items():
    run = subprocess.run(
        ["lean", "--stdin"],
        input=base + suffix + "\nend Colony.Examples.FilterExperiment\n",
        text=True, capture_output=True)
    print("CASE", label, "EXIT", run.returncode)
    print(run.stdout, end="")
    print(run.stderr, end="")
'
```

Output was `positive_by_colony EXIT 1`, `invalid_by_colony EXIT 1`, and `manual_and_controls EXIT 0`. The axiom query reported `[propext, Quot.sound]`, with no `sorryAx`. An earlier candidate theorem bounded the output by the *input length*; `by colony` also failed, and I replaced that candidate because its length-three premise was unused. An initial manual proof attempt using `split_ifs` failed as an unknown tactic; the accepted manual proof uses `by_cases`.

**Assurance and limits:** The streamed manual theorem received Lean elaborator/kernel acceptance only. There was no exported replay, independent-kernel check, Cardano correspondence check, or successful `by colony` proof. Source streaming checked the current tactic text without building a Colony module; no file was changed. `git diff --check` and `node --check observatory/dist/app.js` passed. The repository acceptance criterion for a durable artifact under `research/` remains unmet by the reviewed commit.
