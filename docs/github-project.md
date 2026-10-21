# GitHub Project board

Scope: mirror this repository's issues and pull requests into one public GitHub Projects v2 board. Acceptance: plan without writing by default; add each content item once; update only its Status; derive lanes from recorded facts; retain blockers rather than mark unmerged work complete. This integration does not grant agents publication, merge, or policy authority.

Configure `project.github_project_url` in `colony.json`, or pass `--project-url https://github.com/users/OWNER/projects/NUMBER`. Organization URLs use `/orgs/OWNER/projects/NUMBER`. `--owner`, `--number`, and `--owner-type user|organization` are an alternative. The board must already be public and open, with a single-select **Status** field containing exactly these spellings (additional options are allowed):

| Status | Recorded evidence |
| --- | --- |
| Todo | Open issue without an explicit status or active linked PR |
| Ready | Issue labelled `ready` or `status:ready`, or a fresh ready Colony task |
| In progress | Draft PR, explicit issue label, or fresh authoring/running task |
| In review | Open PR awaiting review, CI, or merge |
| Blocked | Changes requested, failed current-head checks, conflicts, closed unmerged PR, or fresh failed/blocked/intervention task or controller integration hold |
| Done | Closed GitHub issue or merged GitHub PR |

Issue labels `blocked`/`status:blocked`, `in progress`/`status:in-progress`, and `in review`/`status:in-review` are also supported. A GitHub closing-issue reference links an issue to its PR. A merged PR alone does not close or complete an open issue. Formal GitHub changes-requested reviews and controller-authored Colony `changes_requested` or `reject` review comments matching the current commit both block a PR; old-commit comments do not. `--review-author` selects that controller login and defaults to the repository owner. These are board indicators, not merge approval.

## Local use

The script uses Python's standard library and `gh api graphql`. It uses the current authenticated `gh` identity, including the CLI keyring, without extracting or saving its token. An unauthenticated or insufficiently authorized request stops with a safe error. It never refreshes authentication or requests new scopes itself.

```sh
python3 scripts/sync_github_project.py --dry-run
python3 scripts/sync_github_project.py --apply
```

Only `--apply` permits mutations: add missing issue/PR items and change their Status. The script validates the public project, public repository, and all expected Status options before writing. It never creates projects, edits their schema/visibility, removes items, changes issues, or merges PRs. Repeated successful runs make no changes when the board already matches. Requests are bounded to 60 seconds each within a five-minute sync deadline, and all repository/project pages are read before the first write. If a write fails midway, already completed changes remain; another run reconciles them. Serialize callers for one board, as the Actions workflow does.

Optional fresh local evidence:

```sh
python3 -m colony export --output .colony/project-state.json
python3 scripts/sync_github_project.py --state-file .colony/project-state.json --apply
```

For a controller-owned recurring local job, `--state-url http://127.0.0.1:7331/api/state` reads the current local Observatory instead. It permits only a literal loopback HTTP `/api/state` endpoint, disables proxies and redirects, caps the response at 4 MiB, and times out after ten seconds. Unavailable or stale local evidence stops the run before any board write. The job can use the existing `gh` keyring; no token must be copied into its command or environment. It needs the absolute `--config` path when its working directory differs. The script can also be scheduled by the independent local service below.

### Recurring local service on macOS

```sh
python3 -m colony project-service install --port 7331 --interval 120
python3 -m colony project-service status
python3 -m colony project-service stop
python3 -m colony project-service start
python3 -m colony project-service uninstall
```

Installation validates the configured repository and Project URL and pins only the reviewed sync script and minimal target configuration under the ignored `.colony/project-sync/` directory. It installs a separate user LaunchAgent that runs on load and every 120 seconds by default; intervals from 30 seconds to one day are supported. launchd runs at most one instance of that job, and there is no KeepAlive retry loop. If the Observatory, GitHub, or the network is unavailable, the attempt fails and the next scheduled interval tries again. Status distinguishes a loaded periodic job from a running process and reports its most recent exit code.

This service uses the existing local `gh` CLI authentication. It does not copy credentials, configure an Actions secret, call a model, change the colony's runtime caps, or start/stop the controller. Its stdout and stderr stay in ignored local logs. Source/configuration changes require an explicit reinstall to replace the pinned deployment. Stop unloads the periodic job; uninstall removes its LaunchAgent and metadata while retaining deployed files and logs as local evidence.

Exports older than five minutes or more than one minute in the future are rejected; `--state-max-age` can set the allowed age explicitly. Task association uses the exact recorded `pr_url`, an exact `TASKID:` title prefix, or `<!-- colony-task:TASKID -->` in an item body. Cycles are associated by task ID. Recorded authoring/publication maps to In progress, review/CI/merge to In review, and intervention/failure or a governance candidate awaiting controller integration to Blocked. An explicitly `budget_limited` controller blocks queued author/reviewer work. It does not label an executing worker blocked just because its reservation has consumed the remaining budget. Live GitHub terminal state and concrete GitHub blockers take precedence. A local `done` task cannot mark an open GitHub item Done.

Without `--state-file`, the board reflects GitHub only. It cannot infer local leases, model activity, runtime limits, paused cycles, or offline recovery. Internal tasks with no GitHub issue/PR are not created as project drafts. Manual moves to another lane may be overwritten on the next sync; labels, GitHub lifecycle, or Colony state are the inputs.

## Actions setup

`.github/workflows/project-board.yml` reconciles on issues, PRs, review comments, CI completion, an hourly schedule, and manual dispatch. It checks out the repository's default branch, never a contributor's PR code, and uses no issue/PR body text in shell commands. Its board writes do not modify repository content or run model workers.

The workflow is inactive until a controller configures a repository secret named **PROJECTS_TOKEN** with access to the intended project. An existing local `gh` login is not copied to Actions. `GITHUB_TOKEN` is repository-scoped and cannot access user/organization Projects. For a user-owned public project, a dedicated classic token needs `project` scope and access to the repository; a GitHub App with Projects read/write and repository issue/PR read access is an alternative for organization projects. Never put a token in `colony.json`, tracked files, workflow variables, or a public log. Token creation and installation are separate controller actions.

The workflow reads the project URL from `vars.COLONY_PROJECT_URL` when supplied, otherwise from committed configuration. Missing token produces a visible workflow summary and performs no sync. A token/configuration/API failure fails the job rather than claiming synchronization. Hourly reconciliation catches events emitted by another workflow's `GITHUB_TOKEN`, which can suppress event-triggered workflow runs. No local Colony state is available in Actions, so those runs use GitHub evidence only.

GitHub's primary documentation: [Projects GraphQL API](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects) and [Projects with Actions and authentication](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions).
