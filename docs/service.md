# The persistent local service

The controller and the live Observatory run together as a macOS user LaunchAgent.
Launchd owns the process, so ending a chat or closing a terminal does not stop it.
`KeepAlive` restarts the controller after an unexpected exit, with a 30 second
restart throttle. The controller also holds a singleton lock and reconciles its
durable cycles before doing more work.

The reviewed runtime admits up to four independent model jobs concurrently.
Stopping it closes admission and lets existing bounded calls drain before
releasing the singleton. The LaunchAgent shutdown deadline includes the longest
configured model timeout plus cleanup time. Abrupt termination still requires
conservative reconciliation of unfinished reservations.

Install from the reviewed checkout with `python3 -m colony service install`.
The default live dashboard is `http://127.0.0.1:7331/`. The CLI also exposes
`service status`, `service stop`, `service start`, and `service uninstall`.
Stop unloads the job, including its restart policy. Uninstall removes its user
LaunchAgent and installation metadata; it retains the database, logs, worktrees,
and deployed runtime copies as evidence.

Each installation copies the controller package, trusted configuration, and
dashboard into a new ignored local deployment directory. The LaunchAgent invokes
that pinned copy with an explicit Python executable and PATH. The operational
repository remains separate. Merging a PR cannot silently replace the controller,
its allowed paths, its publication policy, or its runtime budget. Installing a
reviewed runtime again is an explicit controller maintenance action.

The plist stores paths and the two environment settings needed to locate tools
and flush output. It stores no access token. Codex and GitHub use the owner's
existing local authentication. Logs and deployment metadata stay under the
ignored local state directory. A user LaunchAgent requires a logged-in user
session; it is not an always-on remote host and cannot make progress while the
machine is asleep or switched off.

The Observatory reports the controller heartbeat independently from its HTTP
connection. A reachable dashboard does not imply an active controller. It shows
stale heartbeats, stopped services, waiting cycles, budget exhaustion, remaining
aggregate worker time, and the actual PR, review, and CI evidence. Hosted saved
snapshots describe their recorded time and do not claim that the controller is
currently alive.
