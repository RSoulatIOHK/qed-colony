# Autonomous publication pipeline

The persistent controller takes a ready task through an isolated Git worktree,
a bounded author attempt, a public pull request, a separate read-only model
review, required GitHub CI, and an exact-head squash merge. The released Lean
tactic does not call an LLM. Researchers develop it using models.

The controller starts with a smaller model and escalates after bounded failures
or revision requests according to `colony/model_policy.py`. Proof implementation
reviews begin at the stronger review tier. Every actual attempt records the
selected model, reasoning effort, token usage, and elapsed wall time. Model
choice never relaxes review, CI, theorem preservation, or proof checking.

## Durable stages

Each task has one cycle in SQLite. The stages are `queued`, `authoring`,
`publishing`, `reviewing`, `review_publication`, `ci`, `merging`, and `done`.
`failed`, `blocked`, and `needs_review` stop that cycle. The original task stays
in review until the controller verifies the merge. A stopped cycle remains
visible and does not prevent other scoped tasks from progressing.

The author and reviewer have separate ephemeral model contexts. Review comments
explicitly identify themselves as model reviews published by the controller's
GitHub account; they do not impersonate another person's approval. Revisions
and failed-review retries are bounded. A failed CI check supplies bounded actual
failure output to the next author attempt.

The publication branch and cycle marker allow PR creation to be reconciled after
a network interruption. Review publication resumes from a saved review without
rerunning the model. Merging requires the reviewed SHA to equal GitHub's current
PR head and every required check to succeed. `gh pr merge` receives
`--match-head-commit`; no administrator override is used. An external merge that
lacks the saved exact-head review and CI evidence is marked as needing review,
rather than counted as a verified colony success.

An interrupted model attempt retains its entire reserved budget and is not
blindly repeated. Uncertain local mutations, including a crash between making
a Git commit and persisting its SHA, conservatively require review. This initial
controller does not automatically resolve conflicts with a moving base branch.

## Publication scope

Engineering workers can propose changes only to `lean/Colony/Tactic.lean`,
`lean/Colony.lean`, `lean/Colony/Procedures/`, `lean/Colony/Examples/`, and
`research/`. Other roles produce research artifacts under `research/colony/`.
Research evidence cannot be deleted automatically. The model reviewer must
check the original task's acceptance criteria, including whether implementation
is required; writing a proposal does not satisfy an implementation requirement.

Policy, challenge statements, benchmark specifications, evaluators, runtime
code, CI, and toolchain configuration are outside routine publication scope.
Those changes require a separate governance PR. The broker validates the
working copy, index, and committed candidate differences, including rename
source paths. It rejects worker-created commits, unexpected branches, symlinks,
unsupported file modes, oversized content, credential patterns, and machine
paths before staging a publication commit. Git hooks are disabled for broker
commands. Candidate code is executed by GitHub CI, not by the privileged
publication broker.

These checks are operational guardrails for cooperative agents. A local Codex
workspace sandbox and Git worktree do not isolate the user's credential stores
from a malicious process with the same operating-system identity. Separate
machines or independently administered containers and a credential broker remain
future hardening work; the initial controller does not claim adversarial isolation.

When the runnable queue empties, a bounded read-only planner proposes one to
three narrow tasks with explicit acceptance criteria. New work is real model
output rather than synthetic dashboard activity. Daily reservations cover
planning, authorship, revisions, and review, so exhausting the cap pauses model
dispatch while CI polling and reconciliation can continue.
