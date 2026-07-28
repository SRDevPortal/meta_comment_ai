#!/usr/bin/env python3
"""Bounded HTTP load test for Meta Comment AI endpoints.

Example:
  META_API_TOKEN="key:secret" python scripts/load_test.py \
    --url http://site1.local:8000 \
    --endpoint /api/method/meta_comment_ai.api.inbox.get_comments
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request


def request_once(url: str, token: str, timeout: int) -> tuple[int, float]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"token {token}"
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers),
            timeout=timeout,
        ) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    return status, time.perf_counter() - started


def percentile(values: list[float], fraction: float) -> float:
    return values[min(len(values) - 1, int(len(values) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--endpoint",
        default="/api/method/meta_comment_ai.api.inbox.get_comments",
    )
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()
    if not 1 <= args.requests <= 10000:
        parser.error("--requests must be between 1 and 10000")
    if not 1 <= args.concurrency <= 100:
        parser.error("--concurrency must be between 1 and 100")

    query = urllib.parse.urlencode({"limit": min(max(args.limit, 1), 200)})
    target = f"{args.url.rstrip('/')}{args.endpoint}?{query}"
    token = os.environ.get("META_API_TOKEN", "")
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(
            pool.map(
                lambda _: request_once(target, token, args.timeout),
                range(args.requests),
            )
        )
    elapsed = time.perf_counter() - started
    latencies = sorted(result[1] for result in results)
    report = {
        "requests": len(results),
        "successes": sum(200 <= result[0] < 300 for result in results),
        "status_counts": {
            str(status): sum(result[0] == status for result in results)
            for status in sorted({result[0] for result in results})
        },
        "requests_per_second": round(len(results) / elapsed, 2),
        "mean_ms": round(statistics.mean(latencies) * 1000, 2),
        "p50_ms": round(percentile(latencies, 0.50) * 1000, 2),
        "p95_ms": round(percentile(latencies, 0.95) * 1000, 2),
        "p99_ms": round(percentile(latencies, 0.99) * 1000, 2),
        "max_ms": round(max(latencies) * 1000, 2),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["successes"] == report["requests"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
