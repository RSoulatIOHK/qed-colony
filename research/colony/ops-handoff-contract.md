# Minimal author-to-reviewer handoff evidence contract

Task `OPSFOLLOW-99de2e987d074fd2a5a74734c6357bbc-1`; inspected base `2aa0e88935e22bb3d5ed744eb96b20da9de08111`. The four inspected files—`colony/pipeline.py`, `colony/worker.py`, `colony/autonomy_store.py`, and the OPS001 PR #10 review comments—are pinned to that base (code) / linked PR record (comments). The comments are [initial review](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313490097), [attribution correction](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313915781), and [later feedback](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6314061023). The initial review reported absent repository-reading tools; later feedback corrected evidence attribution and asked for bounded follow-ups and clear SRE sequencing. The cited 24m10s between comments is elapsed wall time, not reviewer execution or queue time.

## Proposed single record

One record per handoff, keyed by cycle, carries the following **eight fields maximum**. Timestamps are UTC ISO-8601; they mean observed event instants, not inferred durations. Missing values stay null with the stated reason; never backfill from an undated snapshot.

| Field | Source | Timestamp meaning | Missing-data rule |
|---|---|---|---|
| `cycle_id` | autonomy cycle in `autonomy_store.py` | none | null if no durable cycle identity |
| `author_finished_at` | successful `_author` completion in `pipeline.py` | author stage completion observed by controller | null if no completion event |
| `publication_started_at` | entry into `publishing` in `pipeline.py` | controller began publication stage | null if no stage-start observation |
| `publication_finished_at` | successful `pr.published` event in `pipeline.py` | publication handoff completed | null if no successful publication |
| `reviewer_started_at` | reviewer attempt reservation/start in `autonomy_store.py` / `_job` | reviewer call began after ledger reservation | null if no reviewer call started |
| `head_sha` | publication result / cycle head in `pipeline.py` | none | null unless the exact published head is known |
| `failure` | worker result in `worker.py`; otherwise null | event detection instant, UTC | null when no failure; on event overflow include `kind="per_event_output_limit"`, `limit_bytes=1048576`, and observed bytes if measured, else null |

The record must preserve stage-specific timestamps; a total handoff duration may be calculated only when both endpoint timestamps are present. It does not attribute time to intermediate stages without their own observations. The worker currently stops when an event exceeds 1,048,576 bytes and the stream exceeds 8,388,608 bytes total; these limits and the 480-second author / 240-second review caps are unchanged by this proposal.

## Examples (illustrative evidence states)

- **Reported 38 seconds:** one supplied aggregate says author/publication/reviewer handoff took 38 seconds; no constituent timestamps were supplied. Record the aggregate only in accompanying narrative as “reported, stage split unknown”; leave the relevant timestamp fields null. Do not derive stage durations.
- **Event limit:** worker detects one event above 1,048,576 bytes. Persist `failure.kind="per_event_output_limit"`, `limit_bytes=1048576`, and observed size only if measured. Stop the call under existing enforcement; do not retry beyond existing policy.
- **Older snapshot:** snapshot generated at `2026-10-21T09:12:40.745Z` has tasks but no cycles. Treat it as a historical snapshot with cycle/handoff fields unavailable; do not reconcile it against later live state or infer a defect.

## Boundaries and next slice

Smallest later implementation slice: add timestamped handoff-event persistence and the explicit per-event-limit failure record, with focused tests. Permitted paths for that separate assignment: `colony/pipeline.py`, `colony/worker.py`, `colony/autonomy_store.py`, and focused tests `tests/test_pipeline.py`, `tests/test_worker.py`, `tests/test_autonomy_store.py`. This proposal adds no instrumentation. Snapshot reconciliation, outage recovery, dashboards, alerting, and changes to runtime/output enforcement or retry limits are out of scope. Preserve SRE001 ownership of outage recovery.

Admission is serialized and each actual author/reviewer call is reserved through the shared autonomy ledger before launch. Earmark no more than 3,600 seconds and 12 attempts for this cycle including existing retries; defer admission if that full envelope is unavailable. Record actual calls and charges, stop on exhaustion, and report incomplete rather than expand scope. This document makes no reservation or claim that capacity is available. Submit this proposal in its own public SRE governance PR for exact-head independent review and required CI. Any controller change needs a separately bounded assignment and controller integration; this worker does not publish or change the pinned deployment.
