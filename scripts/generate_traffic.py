#!/usr/bin/env python3
"""Generate request traffic against an endpoint for demo/observability purposes.

Usage:
    python scripts/generate_traffic.py
    python scripts/generate_traffic.py --url http://5.161.250.79:8001/slow --workers 10 --duration 120
    python scripts/generate_traffic.py --url http://5.161.250.79:8001/slow --requests 200 --workers 5
"""

import argparse
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Stats:
    ok: int = 0
    failed: int = 0
    lock: threading.Lock = None

    def __post_init__(self):
        self.lock = threading.Lock()

    def record(self, success: bool) -> None:
        with self.lock:
            if success:
                self.ok += 1
            else:
                self.failed += 1


def hit(url: str, timeout: float, stats: Stats) -> None:
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            resp.read()
            elapsed = time.monotonic() - start
            print(f"[{resp.status}] {url} in {elapsed:.2f}s")
            stats.record(True)
    except urllib.error.URLError as exc:
        elapsed = time.monotonic() - start
        print(f"[ERROR] {url} in {elapsed:.2f}s: {exc}")
        stats.record(False)


def worker(url: str, timeout: float, stop_at: float | None, remaining, lock, stats: Stats) -> None:
    while True:
        if stop_at is not None:
            if time.monotonic() >= stop_at:
                return
        else:
            with lock:
                if remaining[0] <= 0:
                    return
                remaining[0] -= 1
        hit(url, timeout, stats)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://5.161.250.79:8001/slow", help="Endpoint to hit")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--requests", type=int, default=100, help="Total requests to send (ignored if --duration is set)")
    parser.add_argument("--duration", type=float, default=None, help="Run for this many seconds instead of a fixed request count")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds")
    args = parser.parse_args()

    stats = Stats()
    stop_at = time.monotonic() + args.duration if args.duration else None
    remaining = [args.requests]
    lock = threading.Lock()

    threads = [
        threading.Thread(target=worker, args=(args.url, args.timeout, stop_at, remaining, lock, stats))
        for _ in range(args.workers)
    ]

    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - start

    print(f"\nDone in {elapsed:.1f}s — ok={stats.ok} failed={stats.failed}")


if __name__ == "__main__":
    main()
