# Minimal author-to-reviewer handoff evidence contract

Task `REPAIR-4eb0f42b67bb49949ccd5b6162642044`. Inspected `colony/pipeline.py`, `colony/worker.py`, `colony/autonomy_store.py` at base `2aa0e88935e22bb3d5ed744eb96b20da9de08111`, source PR #24 candidate `7ae2bffbb5cdcbb3b6abe604d14ee9a7aab3ad00`, and OPS001 PR #10 [review comments](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313490097), [attribution](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6313915781), [scope](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6314061023), [source correction](https://github.com/RSoulatIOHK/qed-colony/pull/10#issuecomment-6314170163). Feedback requires dated evidence, bounded/sequenced follow-ups and accurate attribution. OPS001 reports 38 seconds with no stage split. This repairs PR #24's failure-retention gap.

## Proposed handoff record

One record per `(cycle_id, revision)` with **eight top-level fields**. Times are observed UTC ISO-8601 instants. Proposed observations are not all persisted at base. Missing values remain null with reason; never backfill from snapshots.

| Field | Source | Timestamp meaning | Missing-data rule |
|---|---|---|---|
| `cycle_id` | autonomy cycle | none | null if no durable identity |
| `revision` | `pipeline.py` author revision / `_revise` | none | null if unknown; never join across revisions |
| `author_finished_at` | successful `_author` in `pipeline.py` | controller-observed completion | null if no completion event |
| `publication_started_at` | proposed observation before `broker.commit` | first actual publication attempt | null if unobserved; phase entry is queueing |
| `publication_finished_at` | successful `pr.published` event | publication completion | null absent successful publication |
| `reviewer_started_at` | proposed observation after reviewer `subprocess.Popen` in `worker.py` | reviewer process launch | null if unobserved; reservation/job-start is not launch |
| `head_sha` | successful publication result | none | null until exact revision head is known |
| `failures` | proposed worker output-limit event joined to ledger attempt | nested `detected_at`: observed UTC detection instant | empty if none known; missing members null with reason `not_recorded` |

Bind observations to this revision and published head. New revisions start with null timestamps/head and empty failures; never inherit evidence, even for identical heads. Keep old records. `_revise` does not clear `head_sha`, and cycle updates retain unspecified data, so isolate revisions explicitly. Retries keep original timestamps; associate reviewer starts with actual revision/head. Derive durations only from known ordered endpoints sharing revision/head.

## Per-attempt output-limit failure record

Append a failure object for **every** per-event overflow; never overwrite or deduplicate. Members: `handoff_revision`, ledger `attempt_id`, `failed_stage`, `kind`=`per_event_output_limit`, `limit_bytes`=1,048,576, `detected_at`, `observed_bytes`, `charged_seconds`. Link exact revision and unique shared-ledger attempt (not worker run ID). Stage is author/reviewer plus known detail. Detection time is threshold detection, not call finish; size is measured event bytes; charge is finished ledger charge. Unknown members/linkage stay null with `not_recorded`; never estimate or discard. Retain all entries for cycle/handoff lifetime. If reservation unavailable, defer and launch no call.

`pipeline._job` reserves before model selection/launch; the ledger records ID, stage, status, times and charge. Worker limits remain 480 seconds/author, 240/review, 1,048,576 bytes/event, 8,388,608 bytes total streamed output; overflow stops the call. Enforcement/retry limits stay unchanged. Each repeated review is a distinct attempt. Earmark at most 3,600 seconds/12 attempts per cycle including retries; reserve every call through ledger, stop on exhaustion, return incomplete.

## Examples

- **38-second aggregate:** reported handoff total is 38 seconds, but constituent timestamps are absent. State “stage split unknown”; leave timestamps null and derive no durations.
- **Event-limit failure:** an event exceeds 1,048,576 bytes. Append an entry with this revision and ledger attempt ID, failed stage, limit and detection time; use null plus `not_recorded` for unavailable measured size or charge. Stop the call under existing enforcement and retry policy. Do not overwrite earlier failures.
- **Older snapshot:** snapshot timestamp `2026-10-21T09:12:40.745Z` contains tasks but no cycles. Record those handoff fields as unavailable; do not reconcile with later live state or allege a defect.

## Boundaries and next slice

Smallest later slice: persist revision-scoped observations and append-only failures; carry structured worker overflow and ledger ID. Test no overwrite, revision isolation (including identical heads), launch vs reservation, and missing endpoints/charges. Permitted paths: `colony/pipeline.py`, `colony/worker.py`, `tests/test_pipeline.py`, `tests/test_worker.py`; reuse, do not edit, `autonomy_store.py`. Instrumentation is later. Snapshot reconciliation, outage recovery, dashboards and alerting are out of scope. Preserve SRE001 recovery ownership. Independent of I001 mapping, distinct artifact; serialize follow-up admission.

No instrumentation is implemented. This author made no model-worker call; no ledger attempt ID/charge applies. Existing cycle-call charges were not exposed, so capacity is unknown. Controller must record actual calls/charges, defer if envelope unavailable, and stop on exhaustion. Proposal requires its own public SRE governance PR, exact-head independent review and required CI. This worker cannot open PRs; later controller change needs a separate bounded assignment and integration. No deployment or proof-assurance claim.
