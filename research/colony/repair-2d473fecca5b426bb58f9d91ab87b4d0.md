# Add the nested-loop invariant experiment artifacts

Task `REPAIR-2d473fecca5b426bb58f9d91ab87b4d0`; base revision `097a4117c7f7038f8d448217d7836a0d95d41bbe`.

## Result

The two required files were **not created**. This workspace is read-only, and `lake build Colony` confirmed it cannot write under `lean/.lake`. The task’s artifact acceptance criteria remain unmet.

## Inspection and checks

- The checkout is at `097a4117c7f7038f8d448217d7836a0d95d41bbe` on the task branch, with a clean working tree.
- The supplied candidate commit `fab8d50796e568c6d71d1344aa6ef638885459c7` exists, but its tree does not contain either requested deliverable. It contains a prior research note with a proposed Lean source and recorded in-memory probe outcomes.
- `lake build Colony` failed with `operation not permitted` while attempting to write to `lean/.lake`; this is not evidence about whether the proposed Lean file builds.
- The linked PR page could not be fetched in this environment.

The prior note reports an unchanged equality-preservation theorem proved by direct induction in an assembled in-memory Lean run, while `colony` failed to close that theorem. It also describes a concrete non-vacuity example and a nearby false control. Those are **reported prior probe results**, not results I reproduced from checked-in deliverables at this checkout. The standalone file was absent, so its build and source identity at this candidate head remain unverified.

No tactic, imports, or repository files were changed. No new proof assurance is established here; exported replay, independent-kernel acceptance, and Cardano correspondence remain unverified.
