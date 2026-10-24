"""
PhishSentinel AI — Simple Load Test
--------------------------------------------
A deliberately lightweight load test using only the standard library
(urllib + concurrent.futures) — no Locust/k6 install needed, so it runs
anywhere Python does, including on the same machine you're demoing on.

This won't replace a real load-testing tool for a production system, but
it's enough to produce real numbers for your report's "load testing"
line item: requests/sec, error rate, and p50/p95/p99 latency against
your actual running backend.

Usage:
    # Make sure the backend is running first (uvicorn or docker compose)
    python training/load_test.py --url http://localhost:8000/analyze/url \\
        --requests 200 --concurrency 20

    # Against a deployed instance with an API key configured:
    python training/load_test.py --url https://your-deployment/analyze/url \\
        --requests 200 --concurrency 20 --api-key YOUR_KEY
"""
import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

TEST_URLS = [
    "https://www.google.com/search?q=test",
    "http://paypa1-secure-login.tk/verify/account",
    "https://mybank-online-secure.info/login",
    "http://192.168.1.50/wp-admin",
    "https://www.wikipedia.org/wiki/Phishing",
]


def send_one(base_url: str, api_key: str, index: int):
    payload = json.dumps({"url": TEST_URLS[index % len(TEST_URLS)]}).encode()
    req = urllib.request.Request(
        base_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", **({"X-API-Key": api_key} if api_key else {})},
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception:
        status = 0  # connection error / timeout
    elapsed_ms = (time.perf_counter() - start) * 1000
    return status, elapsed_ms


def percentile(data, pct):
    if not data:
        return 0.0
    data = sorted(data)
    idx = min(int(len(data) * pct), len(data) - 1)
    return data[idx]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/analyze/url")
    parser.add_argument("--requests", type=int, default=100, help="total requests to send")
    parser.add_argument("--concurrency", type=int, default=10, help="concurrent workers")
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()

    print(f"Load testing {args.url}")
    print(f"  {args.requests} requests, concurrency={args.concurrency}\n")

    latencies = []
    statuses = []
    wall_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(send_one, args.url, args.api_key, i) for i in range(args.requests)]
        for f in as_completed(futures):
            status, elapsed_ms = f.result()
            statuses.append(status)
            latencies.append(elapsed_ms)

    wall_elapsed = time.perf_counter() - wall_start
    success = sum(1 for s in statuses if s == 200)
    rate_limited = sum(1 for s in statuses if s == 429)
    errors = sum(1 for s in statuses if s not in (200, 429))

    print("--- Results ---")
    print(f"Wall time:        {wall_elapsed:.2f}s")
    print(f"Throughput:       {args.requests / wall_elapsed:.1f} req/s")
    print(f"Success (200):    {success}/{args.requests}")
    print(f"Rate-limited(429):{rate_limited}/{args.requests}")
    print(f"Other errors:     {errors}/{args.requests}")
    if latencies:
        print(f"Latency p50:      {percentile(latencies, 0.50):.0f} ms")
        print(f"Latency p95:      {percentile(latencies, 0.95):.0f} ms")
        print(f"Latency p99:      {percentile(latencies, 0.99):.0f} ms")
        print(f"Latency mean:     {statistics.mean(latencies):.0f} ms")
        print(f"Latency max:      {max(latencies):.0f} ms")

    print("\nCopy the block above into your report's load-testing section.")
    if rate_limited:
        print(f"Note: {rate_limited} requests hit RATE_LIMIT_PER_MINUTE — that's the ")
        print("rate limiter from app/security.py doing its job, not a failure. Raise")
        print("RATE_LIMIT_PER_MINUTE in .env if you want to measure pure throughput instead.")


if __name__ == "__main__":
    main()
