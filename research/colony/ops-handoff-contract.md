# Minimal author-to-reviewer handoff evidence contract

Task `OPSFOLLOW-99de2e987d074fd2a5a74734c6357bbc-1`; inspected code at base `2aa0e88935e22bb3d5ed744eb96b20da9de08111`: `colony/pipeline.py`, `colony/worker.py`, and `colony/autonomy_store.py`. Also inspected OPS001 PR #10 [initial review](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313490097), [attribution correction](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313915781), [scope feedback](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6314061023), and [source correction](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6314170163). Later reviews required source-backed timing and queue claims, bounded follow-ups, and sequenced SRE work.

## Proposed single record

One record per cycle carries these **seven top-level fields**. Timestamps are UTC ISO-8601 observed instants, not inferred durations. These observations are proposed; the admitted base does not persist the complete record. Missing values stay null with the stated reason; never backfill from an undated snapshot.

| Field | Source | Timestamp meaning | Missing-data rule |
|---|---|---|---|
| `cycle_id` | autonomy cycle in `autonomy_store.py` | none | null if no durable cycle identity |
| `author_finished_at` | successful `_author` completion in `pipeline.py` | author stage completion observed by controller | null if no completion event |
| `publication_started_at` | proposed observation immediately before `broker.commit` in the `publishing` advance in `pipeline.py` | actual publication attempt begins, including commit and PR publication | null if the attempt was not entered or the observation was not recorded; entering `publishing` alone is only queueing |
| `publication_finished_at` | successful `pr.published` event in `pipeline.py` | publication handoff completed | null if no successful publication |
| `reviewer_started_at` | proposed observation after successful reviewer `subprocess.Popen` in `worker.py`, passed to `pipeline.py` | reviewer process launch observed | null if no reviewer process launched or no launch observation was recorded; ledger `started_at` is reservation time, not this field |
| `head_sha` | publication result / cycle head in `pipeline.py` | none | null unless the exact published head is known |
| `failure` | proposed structured result from the per-event threshold check in `worker.py`; otherwise null | nested `detected_at` is the UTC instant the threshold check detects overflow | null unless that check detects overflow; then include `kind="per_event_output_limit"`, `limit_bytes=1048576`, `detected_at`, and `observed_bytes`. If detection time or byte count was not captured, set that member null with reason `not_recorded`; never use job finish time as detection time |

The record must preserve stage-specific timestamps; a total handoff duration may be calculated only when both endpoint timestamps are present. It does not attribute time to intermediate stages without their own observations. In `pipeline._job`, `autonomy_store.reserve_attempt` runs before model selection and executor launch; its `started_at` records reservation only. In `worker.py`, the existing `job.started` event also precedes `Popen` and cannot establish process launch. The worker currently stops when an event exceeds 1,048,576 bytes and the stream exceeds 8,388,608 bytes total; these limits and the 480-second author / 240-second review caps are unchanged by this proposal.

## Examples (illustrative evidence states)

- **Reported 38 seconds:** one supplied aggregate says author/publication/reviewer handoff took 38 seconds; no constituent timestamps were supplied. Record the aggregate only in accompanying narrative as “reported, stage split unknown”; leave the relevant timestamp fields null. Do not derive stage durations.
- **Event limit:** worker detects one event above 1,048,576 bytes. Persist `failure={kind:"per_event_output_limit", limit_bytes:1048576, detected_at:<observed UTC instant>, observed_bytes:<measured count or null>}`. If no detection clock was captured, use `detected_at:null` with reason `not_recorded`; do not substitute job finish time. Stop the call under existing enforcement and retry policy.
- **Older snapshot:** snapshot generated at `2026-10-21T09:12:40.745Z` has tasks but no cycles. Treat it as a historical snapshot with cycle/handoff fields unavailable; do not reconcile it against later live state or infer a defect.

## Boundaries and next slice

Smallest later implementation slice: observe and persist these handoff times in existing cycle data and carry a structured per-event-limit result from worker to pipeline, with focused tests. Permitted paths for that separately bounded assignment: `colony/pipeline.py`, `colony/worker.py`, `tests/test_pipeline.py`, and `tests/test_worker.py`; reuse the existing `autonomy_store.py` cycle update interface without editing it. This proposal adds no instrumentation. Snapshot reconciliation, outage recovery, dashboards, alerting, and changes to runtime/output enforcement or retry limits are out of scope. Preserve SRE001 ownership of outage recovery.

This SRE proposal is independent of the I001 mapping job and uses a distinct artifact. Serialize follow-up admission and reserve each actual author/reviewer call through the shared autonomy ledger before launch. Earmark no more than 3,600 seconds and 12 attempts for this cycle including existing retries; defer admission if that full envelope is unavailable. Record actual calls and charges, stop on exhaustion, and report incomplete rather than expand scope. This document makes no reservation or claim that capacity is available. The controller submits this proposal in its own public SRE governance PR for exact-head independent review and required CI. Any controller change needs a separately bounded assignment and controller integration; this worker does not publish or change the pinned deployment.
