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
    supervise = commands.add_parser("supervise", help="Run the durable autonomous PR/review/CI loop")
    supervise.add_argument("--root", help="Operational repository (default: config directory)")
    supervise.add_argument("--port", type=int, default=7331)
    supervise.add_argument("--once", action="store_true", help="Advance one durable controller step")
    service = commands.add_parser("service", help="Manage the persistent user LaunchAgent")
    service.add_argument("action", choices=("install", "start", "stop", "status", "uninstall"))
    service.add_argument("--root", help="Operational repository (default: config directory)")
    service.add_argument("--port", type=int, default=7331)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        store = Store(args.database or config["database"]).initialize()
        store.autonomy_policy = config.get("autonomy")
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
        elif args.command == "service":
            from . import service as service_control
            root = Path(args.root or Path(args.config).resolve().parent).resolve()
            if args.action == "install":
                result = service_control.install_service(root, Path(args.config).resolve(), store.path, port=args.port)
            else:
                result = getattr(service_control, args.action + "_service" if args.action != "status" else "service_status")(root)
            print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        elif args.command == "supervise":
            import signal
            import threading
            from .server import make_server
            from .supervisor import Supervisor
            from .worker import cleanup_orphan_jobs
            root = Path(args.root or Path(args.config).resolve().parent).resolve()
            policy = dict(config.get("autonomy", {}), _database=str(store.path))
            supervisor = Supervisor(root, store.path, policy, task_store=store)
            supervisor.acquire_lock()
            cleanup_orphan_jobs(root, store.path)
            if args.once:
                try:
                    print(json.dumps(supervisor.tick(), indent=2))
                finally:
                    supervisor.release_lock()
                return 0
            stop = threading.Event()

            def terminate(signum, frame):
                stop.set()
                raise KeyboardInterrupt

            signal.signal(signal.SIGTERM, terminate)
            server = make_server(store, "127.0.0.1", args.port, config["observatory_dir"], config.get("project"))
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.25}, daemon=True)
            thread.start()
            print("Persistent Observatory: http://127.0.0.1:%d" % args.port, flush=True)
            try:
                supervisor.run_forever(stop)
            except KeyboardInterrupt:
                stop.set()
            finally:
                server.shutdown()
                server.server_close()
                supervisor.release_lock()
        return 0
    except (OSError, ValueError, KeyError, PermissionError, RuntimeError) as error:
        print("colony: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
