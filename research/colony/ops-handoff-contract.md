# Minimal author-to-reviewer handoff evidence contract

Task `OPSFOLLOW-99de2e987d074fd2a5a74734c6357bbc-1`. Inspected `colony/pipeline.py`, `colony/worker.py`, and `colony/autonomy_store.py` at base `2aa0e88935e22bb3d5ed744eb96b20da9de08111`; prior artifact at `b83a75ef0d065db8f640bd9c413625beb0640184`. Inspected OPS001 PR #10 [initial review](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313490097), [attribution](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313915781), [scope](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6314061023), and [source](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6314170163) corrections: require dated evidence, bounded follow-ups and sequenced SRE work.

## Proposed single record

One record per handoff, keyed by `(cycle_id, revision)`, has **eight top-level fields**. Proposed observations are not fully persisted at the base. Times are observed UTC ISO-8601 instants. Missing values stay null, with reasons in accompanying evidence; never backfill from an undated snapshot.

| Field | Source | Timestamp meaning | Missing-data rule |
|---|---|---|---|
| `cycle_id` | autonomy cycle in `autonomy_store.py` | none | null if no durable cycle identity |
| `revision` | `pipeline.py` author revision, incremented by `_revise` | none | null if unknown; no cross-record duration |
| `author_finished_at` | successful `_author` completion in `pipeline.py` | author stage completion observed by controller | null if no completion event |
| `publication_started_at` | proposed observation before `broker.commit` in the `publishing` advance in `pipeline.py` | first actual publication attempt begins | null if not observed; entry into `publishing` is only queueing |
| `publication_finished_at` | successful `pr.published` event in `pipeline.py` | publication handoff completed | null if no successful publication |
| `reviewer_started_at` | proposed observation after reviewer `subprocess.Popen` in `worker.py`, passed to `pipeline.py` | first successful process launch for this handoff | null if launch not observed; reservation is not launch |
| `head_sha` | successful publication result in `pipeline.py` | none | null until this revision's exact published head is known |
| `failure` | proposed structured result from per-event threshold check in `worker.py` | nested `detected_at`: UTC overflow detection instant | null unless overflow detected; include `kind="per_event_output_limit"`, `limit_bytes=1048576`, `detected_at`, `observed_bytes`; unrecorded time/count stays null with reason `not_recorded` |

At the base, `_revise` increments revision without clearing `head_sha`; `update_cycle` retains unspecified data. Each new revision creates a fresh record with all four timestamps, head and failure null; preserve older records separately. Never inherit prior head or observations. Bind author/publication observations to this revision's published head; attach reviewer launch only for that revision and exact head. Retries retain original starts; unrecorded starts stay null. Never combine revisions, even if heads match. Calculate durations only with known key/head, both endpoints, verified common handoff/head association and chronological order; otherwise leave them unknown. Intermediate durations need their own endpoints.

`pipeline._job` reserves before model selection and launch; ledger `started_at` is reservation time. Worker `job.started` also precedes `Popen`. Neither establishes reviewer launch. Existing enforcement remains unchanged: 480 seconds/author, 240/review, 1,048,576 bytes/event and 8,388,608 bytes total streamed output; either output overflow stops the call.

## Examples (illustrative evidence states)

- **Reported 38 seconds:** supplied aggregate reports a 38-second handoff without constituent timestamps. Keep “reported, stage split unknown” in accompanying narrative; timestamps stay null. Derive no stage timings.
- **Event limit:** an event exceeds 1,048,576 bytes. Record `failure={kind:"per_event_output_limit",limit_bytes:1048576,detected_at:<observed UTC or null>,observed_bytes:<measured count or null>}`. Uncaptured members stay null, reason `not_recorded`; never substitute job finish time. Stop under existing enforcement/retry policy.
- **Older snapshot:** snapshot at `2026-10-21T09:12:40.745Z` has tasks but no cycles. Handoff fields are unavailable; do not reconcile against later live state or infer a defect.

## Boundaries and next slice

Smallest later slice: persist revision-scoped records and handoff observations, carry structured per-event-limit failure, and test revision isolation (including identical heads), launch vs reservation and missing endpoints. Permitted paths: `colony/pipeline.py`, `colony/worker.py`, `tests/test_pipeline.py`, `tests/test_worker.py`; reuse `autonomy_store.py` without editing it. Implementation/instrumentation, snapshot reconciliation, outage recovery, dashboards and alerting remain outside this first stage. Runtime/output enforcement and retry limits stay unchanged. Preserve SRE001 outage-recovery ownership.

Independent of I001 mapping, with a distinct artifact. Serialize follow-up admission; earmark at most 3,600 seconds/12 attempts per cycle including existing retries, deferring if the envelope is unavailable. Reserve each actual author/reviewer call through the shared ledger before launch; record calls/charges, stop on exhaustion and return incomplete rather than expand scope. No capacity/reservation claim is made here. This author revision launches no additional model calls; prior/current ledger charges are unavailable to this worker and require controller evidence.

The proposal's own public SRE governance PR requires independent exact-head review and required CI. Prior-head checks do not approve this revision. Later controller changes need a separately bounded assignment and controller integration. Worker publication and deployment are excluded.
