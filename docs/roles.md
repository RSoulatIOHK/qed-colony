# Swarm roles and handoffs

Roles describe real execution profiles. A historical name in the worker roster
does not represent a permanently running model. Jobs launch on demand and all
planning, implementation, review, and operations audits share the same daily
runtime and attempt caps.

| Role | Responsibility | Execution and handoff |
| --- | --- | --- |
| Researcher | Investigate architectures, semantics, and experiments | Read-only; publish an evidence-backed research artifact for independent review. |
| Engineer | Implement and test the local Lean tactic | Write only permitted tactic, example, and research paths; independent exact-head review and CI precede routine integration. |
| SRE | Reliability, recovery, and controller process improvements | Write a fixed set of controller, test, and runbook files in a separate governance PR. After independent review and CI it awaits controller integration. The worker cannot merge or deploy itself. |
| Operations steward | Audit how the swarm works, identify missing roles, and propose concrete improvements | Read-only structured report. Reviewed and merged reports may create at most three bounded follow-up jobs using existing execution profiles. New-role charters are proposals, not permission grants. |
| Reviewer | Assess an independently authored artifact and exact candidate head | Separate read-only model context; proof and SRE changes start on the stronger review tier. |
| Planner | Refill an empty runnable queue with bounded tasks | Read-only structured planning; it may select an existing role but cannot create execution permissions. |

The steward is scheduled after each batch of three completed or parked
non-operations cycles. There is at most one pending audit. Its own audits and
planning cycles do not trigger another audit. Follow-up generation is bounded by
the queue backlog, and unchanged evidence does not cause repeated audits.

The first SRE assignment is `SRE001`: wait safely through a network outage,
reconcile remote publication state, and resume without duplicate work or
connectivity-driven model escalation. It is tracked in
[public issue #7](https://github.com/RSoulatIOHK/qed-colony/issues/7).
`OPS001` is the first operations audit of routing, handoffs, failed work, and
missing responsibilities.

CI already runs Python/controller checks, JavaScript syntax, Lean seed checks,
and independent-kernel replay. Ordinary reviewed prover PRs can be integrated
automatically. The deployed controller is pinned: proposed SRE changes require
independent controller integration and a separate deployment. This handoff does
not require the human owner to write implementation code.

An operations worker can propose a new role and a job to implement it. The
proposal must name its purpose, ownership, execution profile, and handoffs.
Changing the actual profile or permissions goes through a separate SRE
governance PR. Audit output never directly installs a role, expands authority,
changes a budget, or edits the proof acceptance rules.
