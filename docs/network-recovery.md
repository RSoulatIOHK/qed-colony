# Network outage recovery

The supervisor treats recognized transient Git and GitHub connectivity failures as retryable controller state. It stores `phase=waiting_network`, the phase to resume, retry count, delay, and UTC epoch retry time in the existing cycle record. The schedule doubles from five seconds up to fifteen minutes by default; policy keys `network_backoff_base_seconds` and `network_backoff_max_seconds` may bound it further. Restart preserves the same cycle, branch, head, PR, review, and retry deadline.

When the deadline arrives, the supervisor resumes the saved phase. Publication retries first reconcile the branch and existing PR. Review comments use a cycle/head marker. CI retries fetch the current PR and check rollup. Merge retries fetch the PR before issuing a merge, and the merge uses GitHub's exact reviewed-head guard. These checks make a remote success followed by a lost local response recoverable without creating another PR or merge.

Authentication and authorization errors, invalid candidates, governance handoffs, exhausted daily budgets, and interrupted or uncertain model attempts remain explicit attention or budget states. Connectivity retries do not change author revision or model tier. Model attempts retain the existing reservation and runtime accounting; interrupted attempts remain charged and require review rather than automatic relaunch. A waiting cycle resumes only after the stored backoff expires and its remote operation can be reconciled.

## Operator steps

1. Inspect the cycle phase, `resume_phase`, `network_retry_count`, and `next_retry_at` in controller state.
2. Restore network access. The supervisor polls automatically and retries after the recorded deadline.
3. If the state becomes `needs_review`, inspect its `last_error`; authentication, candidate, and uncertain-process failures require explicit operator handling.
4. For `budget_limited`, wait for the configured daily reset. Do not clear attempt reservations to force a retry.
5. SRE governance candidates that reach `awaiting_controller_integration` still require independent controller integration and deployment.

The classifier is deliberately narrow and matches common subprocess messages. Unknown failures remain attention errors. This local controller state is operational recovery, not a security boundary.
