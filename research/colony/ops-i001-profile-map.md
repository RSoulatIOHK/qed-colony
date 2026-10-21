# I001 execution profile map (governance proposal)

**Basis:** repository base `6441db8b745f6f83aa2029390f2ba77b95180c80`. Inspected `tasks/initial.json` (I001), `docs/roles.md`, and `colony/github_broker.py` at that base. PR #6 review finding is recorded in the repository’s prior operations report: review of head `7b0e3a5` found implementation and replay evidence missing ([review comment](https://github.com/RSoulatIOHK/qed-colony/pull/6#issuecomment-6313027463)). A direct GitHub page fetch was unavailable during this call; this document does not claim fresh PR verification.

## Acceptance criteria mapped to current authority

| I001 criterion / required capability | Current fit or mismatch | Evidence | Handoff owner |
|---|---|---|---|
| Reject changed theorem statements and nonstandard axioms: evaluator must compare protected statements/assumptions and reject prohibited declarations. | **Mismatch.** `infrastructure` has no role entry in `docs/roles.md`; no current profile grants evaluator changes. Engineer is limited to tactic/example paths and research. | I001 task entry; roles table; broker `ENGINEER_FILES`/`ENGINEER_PREFIXES`; PR #6 review found implementation missing. | Controller must define/authorize a profile and integration path. Evaluator changes require separate authorization. |
| Replay exports in a fresh trusted process. | **Mismatch.** Existing worker roles do not authorize evaluator/replay harness changes. Fresh-process replay cannot be asserted from the broker’s path allowlist or publication behavior. | I001 task entry; roles table; broker role path checks. | Controller/evaluator owner, after separately authorized scope and trusted-process design. |
| Verify independent kernels on representative proofs. | **Mismatch.** No current role has explicit toolchain or independent-kernel implementation authority. The roles doc says CI runs independent-kernel replay, but that is not permission to change evaluator/toolchain/CI. | I001 task entry; roles table’s CI description; broker allows SRE only its listed controller files, not Lean/evaluator/CI paths. | Controller plus separately authorized Lean/toolchain and CI owners. |
| Document remaining trusted components and platform requirements. | **Fit for a bounded research artifact only.** Researcher is read-only and may publish evidence-backed research; engineer and SRE may also write `research/`. Documentation alone does not satisfy the three implementation criteria. | Roles table; broker permits `research/` for publication; this artifact’s scope. | Researcher can prepare documentation; controller owns acceptance and any broader profile. |

## Authority boundary

The existing SRE profile permits scoped controller reliability work, including listed broker, pipeline, worker, recovery, tests, and runbook paths. The broker can validate role-specific changed paths and publish a separate SRE governance PR; it states that model processes receive no publication tool, protected CI runs candidate code, and same-user local operation is not credential isolation. `docs/roles.md` requires independent exact-head review and CI, then controller integration; workers cannot merge or deploy themselves.

Those reliability permissions do **not** authorize changing evaluators, trusted challenge/configuration ownership, Lean toolchain or kernel replay, CI/workflows, or host/VM/container isolation. Each needs separate controller authorization and the appropriate governance/integration. No profile is enabled by this proposal. I001’s role/status/acceptance are unchanged.

## Smallest subsequent stage proposed

After controller approval and serialized capacity admission, assign one **read-only researcher** stage: produce `research/colony/i001-rejection-replay-spec.md`, a compact, source-linked matrix for the four unchanged I001 criteria, listing inputs, expected accept/reject outcomes, trust boundary, and evidence needed for later authorized implementation. Prerequisites: freeze the original I001 task and source revision; controller confirms the researcher profile and externally owned challenge/evaluator owner. Limits: one author call ≤480 seconds, one independent review ≤240 seconds, ≤1,048,576 bytes per event, ≤8,388,608 bytes total output; earmark ≤3,600 seconds/12 attempts including existing retries, serialize admission, and defer if shared capacity is unavailable. **Stop** after the one artifact is reviewed or the envelope is exhausted; do not run candidate code or edit evaluator, challenges, toolchain, isolation, CI, broker, or permissions. Defer all implementation criteria and any profile/execution change to separate controller-authorized work.

SRE001 remains the existing owner of network-outage recovery and reconciliation (issue #7); this mapping does not implement or repair SRE001. PR #6’s documented review gap is likewise not repaired by this proposal.

## Call and capacity record

This mapping used 3 local shell/read calls and 2 web calls (one PR page fetch failed; one search did not locate the requested PR). No author/reviewer model call was made in this artifact workflow, and no shared-ledger reservation or charge was visible or made here; therefore the 3,600-second/12-attempt envelope is **not** represented as reserved. Future admission must reserve through the shared ledger and defer if unavailable. No code, role permission, budget, acceptance criterion, or controller behavior was changed.
