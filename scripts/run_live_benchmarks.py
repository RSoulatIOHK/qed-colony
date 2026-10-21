#!/usr/bin/env python3
"""Refresh the pinned strict benchmark against reviewed origin/main, without LLMs."""

import argparse
from pathlib import Path
import signal
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from colony.benchmark_service import BenchmarkError, BenchmarkService, RunAlreadyActive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Operational public-main repository")
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--interval", type=int, default=120)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true", help="Remeasure the same main revision, using the unchanged protocol")
    args = parser.parse_args()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    service = BenchmarkService(args.root, args.state_dir, stop=stop)
    if not args.once:
        service.serve(args.interval)
        return 0
    try:
        service.run_once(force=args.force)
    except RunAlreadyActive:
        return 0
    except BenchmarkError:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
