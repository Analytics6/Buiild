#!/usr/bin/env python3
"""
Load benchmark for the Buiild Complaint RAG backend.

Simulates 10,000+ unique users with batched concurrent workers and reports
throughput, latency percentiles, and error rates.

Usage:
    python scripts/benchmark_load.py --base-url http://127.0.0.1:8000
    python scripts/benchmark_load.py --users 10000 --concurrency 100 --scenarios all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_QUESTIONS = [
    "How do I resolve a billing overcharge complaint?",
    "What is the refund policy for defective products?",
    "How to handle delivery delay complaints?",
    "What steps for subscription cancellation issues?",
    "How to escalate a repeated customer complaint?",
]


@dataclass
class RequestResult:
    scenario: str
    user_id: int
    status_code: int
    latency_ms: float
    error: Optional[str] = None


@dataclass
class ScenarioStats:
    name: str
    total_users: int
    concurrency: int
    requests: int
    successes: int
    errors: int
    duration_s: float
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def throughput_rps(self) -> float:
        return self.requests / self.duration_s if self.duration_s > 0 else 0.0

    @property
    def error_rate_pct(self) -> float:
        return (self.errors / self.requests * 100) if self.requests else 0.0

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_vals = sorted(self.latencies_ms)
        idx = int(len(sorted_vals) * p / 100)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]

    def to_row(self) -> dict[str, Any]:
        return {
            "scenario": self.name,
            "users": self.total_users,
            "concurrency": self.concurrency,
            "requests": self.requests,
            "successes": self.successes,
            "errors": self.errors,
            "error_rate_pct": round(self.error_rate_pct, 2),
            "duration_s": round(self.duration_s, 2),
            "throughput_rps": round(self.throughput_rps, 2),
            "p50_ms": round(self.percentile(50), 2),
            "p95_ms": round(self.percentile(95), 2),
            "p99_ms": round(self.percentile(99), 2),
            "mean_ms": round(statistics.mean(self.latencies_ms), 2) if self.latencies_ms else 0.0,
        }


class BenchmarkRunner:
    def __init__(self, base_url: str, users: int, concurrency: int, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.users = users
        self.concurrency = concurrency
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(concurrency)
        self._results: list[RequestResult] = []

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        scenario: str,
        user_id: int,
        json_body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> RequestResult:
        async with self._semaphore:
            start = time.perf_counter()
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout,
                )
                latency = (time.perf_counter() - start) * 1000
                return RequestResult(scenario, user_id, response.status_code, latency)
            except Exception as exc:
                latency = (time.perf_counter() - start) * 1000
                return RequestResult(scenario, user_id, 0, latency, error=str(exc))

    def _aggregate(self, scenario: str, results: list[RequestResult], duration_s: float) -> ScenarioStats:
        successes = sum(1 for r in results if 200 <= r.status_code < 300)
        errors = len(results) - successes
        stats = ScenarioStats(
            name=scenario,
            total_users=self.users,
            concurrency=self.concurrency,
            requests=len(results),
            successes=successes,
            errors=errors,
            duration_s=duration_s,
            latencies_ms=[r.latency_ms for r in results if r.status_code > 0],
        )
        return stats

    async def run_health(self, client: httpx.AsyncClient) -> ScenarioStats:
        start = time.perf_counter()
        tasks = [
            self._request(client, "GET", "/health", "health_check", i)
            for i in range(min(self.users, self.concurrency * 10))
        ]
        results = await asyncio.gather(*tasks)
        return self._aggregate("health_check", results, time.perf_counter() - start)

    async def run_registration_burst(self, client: httpx.AsyncClient) -> ScenarioStats:
        start = time.perf_counter()
        tasks = [
            self._request(
                client,
                "POST",
                "/register",
                "registration_burst",
                i,
                json_body={
                    "email": f"bench_user_{i}@benchmark.example.com",
                    "password": "benchpass123",
                    "full_name": f"Bench User {i}",
                    "role": "analyst",
                },
            )
            for i in range(self.users)
        ]
        results = await asyncio.gather(*tasks)
        return self._aggregate("registration_burst", results, time.perf_counter() - start)

    async def run_concurrent_logins(self, client: httpx.AsyncClient) -> ScenarioStats:
        """Login with pre-seeded demo users cycling through user IDs."""
        start = time.perf_counter()
        tasks = []
        for i in range(self.users):
            email = "demo@support.ai" if i % 2 == 0 else "admin@support.ai"
            password = "demo123" if i % 2 == 0 else "admin123"
            tasks.append(
                self._request(
                    client,
                    "POST",
                    "/login",
                    "concurrent_logins",
                    i,
                    json_body={"email": email, "password": password},
                )
            )
        results = await asyncio.gather(*tasks)
        return self._aggregate("concurrent_logins", results, time.perf_counter() - start)

    async def _login_token(self, client: httpx.AsyncClient, user_id: int) -> Optional[str]:
        email = "demo@support.ai" if user_id % 2 == 0 else "admin@support.ai"
        password = "demo123" if user_id % 2 == 0 else "admin123"
        result = await self._request(
            client,
            "POST",
            "/login",
            "session_setup",
            user_id,
            json_body={"email": email, "password": password},
        )
        if result.status_code != 200:
            return None
        return None  # token fetched separately in validate/ask flows

    async def run_session_validation(self, client: httpx.AsyncClient) -> ScenarioStats:
        """Create sessions then validate via /me under load."""
        tokens: list[Optional[str]] = [None] * self.users
        login_start = time.perf_counter()

        async def login_one(uid: int) -> None:
            email = "demo@support.ai" if uid % 2 == 0 else "admin@support.ai"
            password = "demo123" if uid % 2 == 0 else "admin123"
            async with self._semaphore:
                try:
                    resp = await client.post(
                        f"{self.base_url}/login",
                        json={"email": email, "password": password},
                        timeout=self.timeout,
                    )
                    if resp.status_code == 200:
                        tokens[uid] = resp.json().get("token")
                except Exception:
                    pass

        await asyncio.gather(*[login_one(i) for i in range(self.users)])

        start = time.perf_counter()
        tasks = []
        for i in range(self.users):
            token = tokens[i]
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            tasks.append(
                self._request(client, "GET", "/me", "session_validation", i, headers=headers)
            )
        results = await asyncio.gather(*tasks)
        stats = self._aggregate("session_validation", results, time.perf_counter() - start)
        stats.duration_s += time.perf_counter() - login_start
        return stats

    async def run_rag_ask(
        self,
        client: httpx.AsyncClient,
        use_cache: bool = True,
        scenario_name: str = "rag_ask",
    ) -> ScenarioStats:
        """Concurrent /ask RAG queries with unique questions per user."""
        login_resp = await client.post(
            f"{self.base_url}/login",
            json={"email": "demo@support.ai", "password": "demo123"},
            timeout=self.timeout,
        )
        token = login_resp.json().get("token", "") if login_resp.status_code == 200 else ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        start = time.perf_counter()
        tasks = []
        for i in range(self.users):
            question = DEFAULT_QUESTIONS[i % len(DEFAULT_QUESTIONS)] + f" (user {i})"
            tasks.append(
                self._request(
                    client,
                    "POST",
                    "/ask",
                    scenario_name,
                    i,
                    json_body={"question": question, "template": "support", "use_cache": use_cache},
                    headers=headers,
                )
            )
        results = await asyncio.gather(*tasks)
        return self._aggregate(scenario_name, results, time.perf_counter() - start)

    async def run_cache_comparison(self, client: httpx.AsyncClient) -> list[ScenarioStats]:
        """Same question repeated: first pass (miss), second pass (hit)."""
        login_resp = await client.post(
            f"{self.base_url}/login",
            json={"email": "demo@support.ai", "password": "demo123"},
            timeout=self.timeout,
        )
        token = login_resp.json().get("token", "") if login_resp.status_code == 200 else ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        question = "What is the standard refund process for billing complaints?"

        async def ask_batch(scenario: str, use_cache: bool) -> ScenarioStats:
            start = time.perf_counter()
            tasks = [
                self._request(
                    client,
                    "POST",
                    "/ask",
                    scenario,
                    i,
                    json_body={"question": question, "template": "support", "use_cache": use_cache},
                    headers=headers,
                )
                for i in range(min(self.users, self.concurrency * 20))
            ]
            results = await asyncio.gather(*tasks)
            return self._aggregate(scenario, results, time.perf_counter() - start)

        miss = await ask_batch("cache_miss", use_cache=False)
        hit = await ask_batch("cache_hit", use_cache=True)
        return [miss, hit]

    async def run_all(self, scenarios: list[str]) -> list[ScenarioStats]:
        limits = httpx.Limits(max_connections=self.concurrency + 10, max_keepalive_connections=self.concurrency)
        async with httpx.AsyncClient(limits=limits) as client:
            all_stats: list[ScenarioStats] = []

            if "health" in scenarios:
                print("Running health_check...")
                all_stats.append(await self.run_health(client))

            if "register" in scenarios:
                print(f"Running registration_burst ({self.users} users)...")
                all_stats.append(await self.run_registration_burst(client))

            if "login" in scenarios:
                print(f"Running concurrent_logins ({self.users} users)...")
                all_stats.append(await self.run_concurrent_logins(client))

            if "session" in scenarios:
                print(f"Running session_validation ({self.users} users)...")
                all_stats.append(await self.run_session_validation(client))

            if "rag" in scenarios:
                print(f"Running rag_ask ({self.users} users)...")
                all_stats.append(await self.run_rag_ask(client, use_cache=True, scenario_name="rag_ask"))

            if "cache" in scenarios:
                print("Running cache_miss vs cache_hit comparison...")
                all_stats.extend(await self.run_cache_comparison(client))

            return all_stats


def print_table(stats_list: list[ScenarioStats]) -> None:
    rows = [s.to_row() for s in stats_list]
    if not rows:
        print("No results.")
        return

    columns = list(rows[0].keys())
    widths = {col: max(len(col), max(len(str(r[col])) for r in rows)) for col in columns}

    header = " | ".join(col.ljust(widths[col]) for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)
    print(header)
    print(separator)
    for row in rows:
        print(" | ".join(str(row[col]).ljust(widths[col]) for col in columns))


async def smoke_test(base_url: str, timeout: float = 60.0) -> dict[str, Any]:
    """Quick smoke test against a live server."""
    results: dict[str, Any] = {"passed": [], "failed": [], "details": {}}
    async with httpx.AsyncClient(timeout=timeout) as client:
        checks = [
            ("health", "GET", "/health", None, None, 200),
        ]
        for name, method, path, body, headers, expected in checks:
            try:
                resp = await client.request(method, f"{base_url}{path}", json=body, headers=headers)
                ok = resp.status_code == expected
                (results["passed"] if ok else results["failed"]).append(name)
                results["details"][name] = {"status": resp.status_code, "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:200]}
            except Exception as exc:
                results["failed"].append(name)
                results["details"][name] = {"error": str(exc)}

        try:
            reg_email = f"smoke_test_{int(time.time())}@benchmark.example.com"
            reg = await client.post(
                f"{base_url}/register",
                json={"email": reg_email, "password": "smoke12345", "full_name": "Smoke Test", "role": "analyst"},
            )
            if reg.status_code not in (200, 400):
                results["failed"].append("register_login")
                results["details"]["register_login"] = {"register_status": reg.status_code, "body": reg.text[:200]}
            else:
                login = await client.post(f"{base_url}/login", json={"email": reg_email, "password": "smoke12345"})
                if login.status_code == 200:
                    token = login.json()["token"]
                    results["passed"].append("register_login")
                    results["details"]["register_login"] = {"email": reg_email, "token_preview": token[:12] + "..."}

                    me = await client.get(f"{base_url}/me", headers={"Authorization": f"Bearer {token}"})
                    if me.status_code == 200:
                        results["passed"].append("session_validate")
                    else:
                        results["failed"].append("session_validate")

                    ask = await client.post(
                        f"{base_url}/ask",
                        json={"question": "How to handle billing complaints?", "template": "support"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if ask.status_code == 200:
                        results["passed"].append("rag_ask")
                        results["details"]["rag_ask"] = {"cached": ask.json().get("cached"), "answer_preview": ask.json().get("answer", "")[:100]}
                    else:
                        results["failed"].append("rag_ask")
                        results["details"]["rag_ask"] = {"status": ask.status_code, "body": ask.text[:200]}

                    ask2 = await client.post(
                        f"{base_url}/ask",
                        json={"question": "How to handle billing complaints?", "template": "support", "use_cache": True},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if ask2.status_code == 200:
                        results["passed"].append("cache_behavior")
                        results["details"]["cache_behavior"] = {"cached": ask2.json().get("cached")}
                    else:
                        results["failed"].append("cache_behavior")
                else:
                    results["failed"].append("register_login")
                    results["details"]["register_login"] = {"login_status": login.status_code, "body": login.text[:200]}
        except Exception as exc:
            results["failed"].append("auth_flow")
            results["details"]["auth_flow"] = {"error": str(exc)}

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Buiild RAG backend load benchmark")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=10000, help="Number of unique users to simulate")
    parser.add_argument("--concurrency", type=int, default=50, help="Max concurrent requests")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--scenarios",
        default="all",
        help="Comma-separated: health,register,login,session,rag,cache or 'all'",
    )
    parser.add_argument("--smoke-only", action="store_true", help="Run smoke tests only")
    parser.add_argument("--output", type=str, default="", help="Save JSON results to file")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    scenario_map = {
        "all": ["health", "register", "login", "session", "rag", "cache"],
        "health": ["health"],
        "register": ["register"],
        "login": ["login"],
        "session": ["session"],
        "rag": ["rag"],
        "cache": ["cache"],
    }

    if args.smoke_only:
        print(f"=== Smoke Test: {args.base_url} ===")
        smoke = await smoke_test(args.base_url, args.timeout)
        print(f"PASSED: {smoke['passed']}")
        print(f"FAILED: {smoke['failed']}")
        print(json.dumps(smoke["details"], indent=2))
        return 0 if not smoke["failed"] else 1

    scenarios = scenario_map.get(args.scenarios, args.scenarios.split(","))

    print(f"=== Buiild RAG Load Benchmark ===")
    print(f"Base URL:    {args.base_url}")
    print(f"Users:       {args.users:,}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Scenarios:   {scenarios}")
    print()

    print("--- Pre-flight smoke test ---")
    smoke = await smoke_test(args.base_url, args.timeout)
    print(f"Smoke PASSED: {smoke['passed']}")
    if smoke["failed"]:
        print(f"Smoke FAILED: {smoke['failed']}")
        print("Aborting benchmark due to smoke test failures.")
        return 1
    print()

    runner = BenchmarkRunner(args.base_url, args.users, args.concurrency, args.timeout)
    stats = await runner.run_all(scenarios)

    print()
    print("=== Benchmark Results ===")
    print_table(stats)

    total_requests = sum(s.requests for s in stats)
    total_errors = sum(s.errors for s in stats)
    total_duration = sum(s.duration_s for s in stats)
    print()
    print(f"Total requests: {total_requests:,}")
    print(f"Total errors:   {total_errors:,}")
    print(f"Total duration: {total_duration:.1f}s (sequential scenarios)")
    print()
    print("Note: 10,000+ users simulated via batched async workers.")
    print("Concurrency represents simultaneous in-flight requests, not 10k open connections.")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "config": {
                "base_url": args.base_url,
                "users": args.users,
                "concurrency": args.concurrency,
            },
            "smoke": smoke,
            "results": [s.to_row() for s in stats],
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Results saved to {output_path}")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
