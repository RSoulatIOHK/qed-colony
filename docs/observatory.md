# The Observatory

The read-only QED Colony dashboard lives in `observatory/dist/`. It is buildless HTML, CSS, and JavaScript with no runtime dependencies. Serve that directory through the colony server for live operation or through any static host for snapshot publication.

## Data contract

The dashboard first requests `/api/state`, then falls back to `./state.json`. Responses must be JSON objects; all collections may be empty or omitted. The runtime contract is:

```json
{
  "schema_version": 1,
  "project": { "name": "QED Colony", "repo_url": "https://github.com/RSoulatIOHK/qed-colony", "mission": "…" },
  "generated_at": "2026-10-21T12:00:00Z",
  "mode": "live",
  "agents": [],
  "tasks": [],
  "events": [],
  "benchmarks": [],
  "reviews": []
}
```

The initial checked-in snapshot is deliberately empty and has no timestamp. Publication should replace it with an actual exported state and set `mode` to `snapshot`. The display identifies data fetched from the static file as a snapshot regardless of its declared mode. It displays the state’s `generated_at`; it does not substitute the browser’s refresh time. A failed refresh retains the last available state and marks the connection unavailable.

The live endpoint is polled every 15 seconds while the page is visible. The refresh control performs a real fetch. All dashboard interactions are local and read-only.

## Views and behavior

- Overview: agents and tasks grouped into research, build, review, and verify lanes; task dependency links; explicit agent assignments; mission; current tasks; recent recorded events.
- Research queue: actual tasks, full-text title/description search, status filter, task details, recorded acceptance criteria, dependencies, branch and PR links, and reviews.
- Kanban: six read-only lanes (Backlog, Ready, In progress, Review, Blocked, Done), task search, role filter, actual PR/issue links, and cycle/review/CI evidence. An exhausted model budget, failed task, requested changes, and governance integration holds stay visible. The overview links directly to the board; `#kanban` opens it on first load. Cards open the existing acceptance-criteria and task-history dialog.
- Proof frontier: actual benchmark reports and explicit trust categories. The run selector defaults to the latest `measured_at` grouped by `run_key`; its label records toolchain and measurement time. The strategy selector defaults to `colony` when available and permits all other reported strategies. Explicit historical run selection persists across refreshes. An absent trust category remains unspecified; `assurance: "none"` and `proof_failed` explicitly show no checked proof. Full recorded evidence is expandable.
- Activity: event history in reverse chronological order with an event-kind filter and links to task details.

The Kanban board projects recorded task status together with the latest cycle for each task; it does not mutate assignments or support dragging cards. Failed tasks and cycles requiring intervention are shown in Blocked. Review and CI are separate gates, so an open PR with green checks is never treated as completed without recorded completion. Model stages that cannot start because the daily budget is exhausted are shown in Blocked; an already active model worker may finish its reserved attempt. Ready tasks without a cycle remain Ready and display that they await the daily budget. Snapshot labels retain the distinction between recorded activity and confirmed live operation.

Set optional `project.github_project_url` (or `project.project_url`) in exported state to show an external “Open GitHub Project” link on the board. It accepts only credential-free HTTPS URLs on `github.com` with `/users/<owner>/projects/<number>` or `/orgs/<owner>/projects/<number>`, optionally ending in `/views/<number>`. The link is hidden for absent or invalid values. The dashboard does not fetch private Project data or embed GitHub authentication; controller-side synchronization owns any Project changes.

The graph shows up to 20 tasks and 12 agents to remain legible; an overflow notice directs visitors to the full queue. Lane assignment is a presentation heuristic based on role or task title. Nodes and edges represent recorded entities and dependencies only. Empty states do not simulate agents, PRs, results, reviews, or activity.

Benchmark objects are displayed using their recorded name/title, status, description/summary/property, known measurement fields, and exact JSON. The runtime’s flattened case records support `track`, `kind`, `strategy`, `wall_seconds`, `axioms`, and `assurance`. An explicit `assurance: "lean_kernel"` renders as kernel checked only for a successful/certified status; failed or unsupported cases show no checked proof. Alternatively, set `trust_category` to `solver_result`, `reconstructed`, or `kernel_checked` only when the recorded evidence establishes that category. Unknown categories render as unspecified. Kernel checking does not imply independent replay; set `independent_replay: false` to show explicitly that independent replay was not performed.

External links require absolute HTTPS URLs without embedded credentials. Arbitrary state text is inserted with DOM text APIs, never interpreted as HTML. The app supports keyboard tabs, Escape to close details, reduced-motion preferences, and mobile layouts. It has no external JavaScript, fonts, or media dependencies and works with a restrictive same-origin CSP.

## Check

```sh
node --check observatory/dist/app.js
```

For visual checks, use the colony server or a local static server and inspect both the empty initial state and an actual exported state. Do not commit fabricated operational fixture data as a public snapshot.
