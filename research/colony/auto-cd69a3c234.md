# Measure generic filtering-procedure verification

Task `AUTO-cd69a3c234`; base revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`.

**AUTO-cd69a3c234 — generic bounded filtering verification**

Read-only research artifact; proposed destination: `research/colony/auto-cd69a3c234.md`. No files were changed and no candidate code was executed.

**Result:** No verified `by colony` success is established. The existing artifact reports positive and invalid attempts failing at an earlier revision. Those measurements were not repeated at the reviewed revision.

| Provenance | Revision |
|---|---|
| Task base | `097a4117c7f7038f8d448217d7836a0d95d41bbe` |
| Historical measurement reported by the existing artifact | `188db44425be47a7609bd56682c8350bb5c0f984` |
| Reviewed checkout, verified this session | `9aa307c4609e3e5514f1278e3ab0474ded901c5d` |

Actual read-only checks:

- `git rev-parse HEAD` returned the reviewed revision above.
- `git status --short --branch` reported a clean checkout.
- `git diff --exit-code 188db44425be47a7609bd56682c8350bb5c0f984 HEAD -- lean/Colony/Tactic.lean lean/Colony/Procedures/ListState.lean lean/lean-toolchain lean/lakefile.toml` exited **0**, with no differences.
- `git diff --stat 188db44425be47a7609bd56682c8350bb5c0f984 HEAD` showed only 102 added lines in the research note.
- `git diff --check` exited **0**.
- File inspection and `git ls-files lean/Colony/Examples` found no filtering harness.

Thus, the relevant sources match the historically reported sources. This does **not** constitute execution of the experiment at the reviewed revision. The quoted “unmeasured” passage describes the earlier artifact state; it must not be presented as the current experiment result.

The procedure preserves input order and retains precisely those elements whose Boolean predicate evaluates to true. The unchanged positive specification quantifies over arbitrary `α : Type`, arbitrary `keep : α → Bool`, and any input list of length at most **3**. It requires the output length to remain at most **3**. There are no additional assumptions.

The bound constrains the theorem’s inputs; it does not configure exhaustive enumeration. The inspected tactic uses its deterministic portfolio with no experiment-specific helper or theorem-name dispatch added. The toolchain file pins Lean `v4.35.0`; historical runs specify no additional resource overrides.

**Proposed standalone harness — not installed or executed**

Destination: `lean/Colony/Examples/FilterBounded.lean`.

```lean
import Colony.Tactic

namespace Colony.Examples.FilterExperiment

def retain {α : Type} (keep : α → Bool) : List α → List α
  | [] => []
  | x :: xs =>
      if keep x then x :: retain keep xs else retain keep xs

theorem retained_length_bounded {α : Type} (keep : α → Bool)
    (xs : List α) (hbound : xs.length ≤ 3) :
    (retain keep xs).length ≤ 3 := by colony

-- Deliberately false: retain every element of a length-three list.
example : True := by
  fail_if_success
    have invalid {α : Type} (keep : α → Bool) (xs : List α)
        (hbound : xs.length ≤ 3) :
        (retain keep xs).length ≤ 2 := by colony
  trivial

-- Non-vacuity, retention, removal, and counterexample controls.
example : ([0, 1, 2] : List Nat).length ≤ 3 := by decide

example :
    retain (fun _ : Nat => true) [0, 1, 2] = [0, 1, 2] := by decide

example :
    retain (fun _ : Nat => false) [0, 1, 2] = [] := by decide

example :
    ¬ (retain (fun _ : Nat => true) [0, 1, 2]).length ≤ 2 := by decide

end Colony.Examples.FilterExperiment
```

The positive proof body is exactly `by colony`. The invalid guard tests tactic failure; it does not establish the false proposition. The concrete length-three witness demonstrates both non-vacuity and invalidity without changing the positive theorem.

**Evidence and failed attempts**

The existing note contains the historical Python command that streamed source into `lean --stdin`; that command did not execute a standalone imported harness.

| Historical attempt, as reported in that note | Reported result |
|---|---|
| Unchanged positive theorem, exactly `by colony` | Exit **1**; `colony: the initial proof portfolio could not close this goal` |
| Invalid output bound `≤ 2`, exactly `by colony` | Exit **1**, same diagnostic |
| Manual positive proof and concrete controls | Exit **0**; not a tactic win |
| Earlier candidate bounding output by input length | Tactic failed; candidate abandoned because its length-three premise was unused |
| Initial manual proof using `split_ifs` | Failed: unknown tactic |

These are historical reports, not independently reproduced measurements. The manual proof is excluded from tactic scoring.

After the proposed harness is installed in an authorized writable checkout, the exact proposed commands, run from the repository root, are:

```sh
git rev-parse HEAD
git status --short
cd lean
lake build Colony.Tactic
lake env lean Colony/Examples/FilterBounded.lean
```

These commands were **not run** here. A future record must capture that checkout’s revision, harness content, diagnostics, and exit status. The invalid guard is a passing rejection check only if Lean actually processes it successfully.

**Assurance and remaining limitations:** This session establishes source inspection and Git consistency only. Historical elaborator/kernel acceptance applies solely to the reported manual proof. No current-revision tactic measurement, successful `by colony` proof, exported replay, independent-kernel acceptance, or Cardano execution correspondence is established. The standalone harness remains proposed, so the requested committed-artifact and measured-harness acceptance criteria remain outstanding.
