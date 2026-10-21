"""Command line entry point: python3 -m colony --help."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from .store import Store


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError("Config must be a JSON object")
    base = path.parent
    for key, default in (("database", ".colony/colony.db"), ("seed_file", "tasks/initial.json"), ("observatory_dir", "observatory/dist")):
        config[key] = str((base / config.get(key, default)).resolve())
    return config


def write_snapshot(snapshot, output):
    """Atomically replace a snapshot so readers never see partial JSON."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + output.name + ".", dir=str(output.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(snapshot, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description="QED Colony durable local control plane")
    parser.add_argument("--config", default="colony.json", help="JSON config (default: colony.json)")
    parser.add_argument("--database", help="Override database path")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create database and idempotently seed tasks")
    init.add_argument("--seed", help="Override seed JSON file")
    commands.add_parser("status", help="Show actual task and agent counts")
    serve = commands.add_parser("serve", help="Serve read-only Observatory and live state")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--static-dir")
    enqueue = commands.add_parser("enqueue", help="Add a task without changing existing IDs")
    enqueue.add_argument("id")
    enqueue.add_argument("title")
    enqueue.add_argument("--role", default="engineer")
    enqueue.add_argument("--priority", type=int, default=0)
    enqueue.add_argument("--depends-on", action="append", default=[])
    enqueue.add_argument("--acceptance", action="append", default=[])
    enqueue.add_argument("--description", default="")
    export = commands.add_parser("export", help="Write an atomic, real state snapshot")
    export.add_argument("--output", help="Default: observatory/dist/state.json")
    run = commands.add_parser("run", help="Run one bounded worker task")
    run.add_argument("--once", action="store_true", help="Run once (the default)")
    run.add_argument("--role")
    run.add_argument("--timeout", type=int, default=180)
    run.add_argument("--agent")
    run.add_argument("--sandbox", choices=("read-only", "workspace-write"), default="read-only")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        store = Store(args.database or config["database"]).initialize()
        if args.command == "init":
            seed_path = Path(args.seed or config["seed_file"])
            if not seed_path.is_file():
                raise ValueError("Seed file does not exist: %s" % seed_path)
            data = json.loads(seed_path.read_text(encoding="utf-8"))
            tasks = data.get("tasks", []) if isinstance(data, dict) else data
            if not isinstance(tasks, list):
                raise ValueError("Seed JSON must be a task list or an object containing tasks")
            print("Initialized %s; added %d tasks" % (store.path, store.seed(tasks)))
        elif args.command == "status":
            recovered = store.recover_expired()
            state = store.snapshot(project=config.get("project"))
            counts = {}
            for task in state["tasks"]:
                counts[task["status"]] = counts.get(task["status"], 0) + 1
            print("%s: %d tasks, %d registered agents" % (state["project"]["name"], len(state["tasks"]), len(state["agents"])))
            print("  " + ", ".join("%s=%s" % item for item in sorted(counts.items())))
            if recovered:
                print("Recovered %d expired leases" % recovered)
        elif args.command == "enqueue":
            count = store.seed([{"id": args.id, "title": args.title, "role": args.role, "priority": args.priority,
                                 "depends_on": args.depends_on, "acceptance": args.acceptance, "description": args.description}])
            print("Added %d task(s)" % count)
        elif args.command == "export":
            output = args.output or str(Path(config["observatory_dir"]) / "state.json")
            snapshot = store.snapshot(project=config.get("project"))
            snapshot["mode"] = "snapshot"
            write_snapshot(snapshot, output)
            print("Exported %s" % output)
        elif args.command == "serve":
            from .server import make_server
            server = make_server(store, args.host, args.port, args.static_dir or config["observatory_dir"], config.get("project"))
            print("Observatory: http://%s:%d" % server.server_address, flush=True)
            try:
                server.serve_forever(poll_interval=0.25)
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        elif args.command == "run":
            from .worker import run_once
            result = run_once(root=Path(args.config).resolve().parent, db_path=store.path,
                              role=args.role, timeout=args.timeout, agent_id=args.agent, sandbox=args.sandbox)
            print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, PermissionError) as error:
        print("colony: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
