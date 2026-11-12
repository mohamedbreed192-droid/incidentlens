"""Measure authenticated incident-creation HTTP latency on the local synthetic baseline demo."""

import argparse
import getpass
import json
import math
import os
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

import httpx

from app.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--output", default="evaluation/http-results.json")
    args = parser.parse_args()
    if (
        urlparse(args.url).hostname not in {"localhost", "127.0.0.1"}
        or settings().analysis_mode != "baseline"
    ):
        parser.error(
            "Use a loopback URL and ANALYSIS_MODE=baseline. This benchmark creates synthetic records."
        )
    password = os.environ.get("DEMO_PASSWORD") or getpass.getpass("Local engineer demo password: ")
    cases = [c for c in json.loads(Path("evaluation/cases.json").read_text()) if "invalid" not in c]
    rows = []
    with httpx.Client(base_url=args.url, timeout=30) as client:
        login = client.post("/api/auth/login", json={"username": "engineer", "password": password})
        login.raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        # Warm connection and auth query; authentication itself is outside the measured request.
        client.get("/api/dashboard").raise_for_status()
        for case in cases:
            started = perf_counter()
            response = client.post(
                "/api/incidents", json={"title": "HTTP evaluation " + case["id"], "log_text": case["log"]}
            )
            elapsed = (perf_counter() - started) * 1000
            response.raise_for_status()
            detail = client.get("/api/incidents/" + response.json()["id"])
            detail.raise_for_status()
            assert detail.json()["report"]["mode"] == "baseline", "Unexpected analysis mode; stop this run"
            rows.append(
                {"case": case["id"], "status_code": response.status_code, "latency_ms": round(elapsed, 3)}
            )
        client.post("/api/auth/logout").raise_for_status()
    values = sorted(row["latency_ms"] for row in rows)
    result = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "conditions": {
            "client_python": platform.python_version(),
            "platform": platform.platform(),
            "url": args.url,
            "analysis_mode": "baseline",
            "requests": "36 valid frozen cases; authenticated once, serial HTTP/1.1 keep-alive; warm app/database; no concurrent load; loopback to Docker FastAPI/PostgreSQL",
            "included": "POST /api/incidents transport, parsing, redaction, authorization, retrieval, report generation, incident/audit persistence, commit, and response body",
            "excluded": "login, subsequent detail verification GET, browser rendering, external model, cold startup",
        },
        "requests": len(rows),
        "successful_creations": sum(r["status_code"] == 201 for r in rows),
        "latency_ms": {
            "median": round(statistics.median(values), 3),
            "p95_nearest_rank": values[math.ceil(0.95 * len(values)) - 1],
            "max": max(values),
        },
        "results": rows,
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
