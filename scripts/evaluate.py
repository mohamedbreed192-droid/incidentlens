"""Run reproducible baseline evaluation against a migrated, seeded PostgreSQL database."""

import asyncio
import json
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from sqlalchemy import select, text

from app.analysis import investigate
from app.config import settings
from app.db import SessionLocal
from app.models import Document, User
from app.parsing import classify, parse_log
from app.redaction import redact
from app.retrieval import retrieve
from app.security import allowed_documents


async def evaluate():
    if settings().analysis_mode != "baseline":
        raise SystemExit("Evaluation must use ANALYSIS_MODE=baseline; it never spends provider credits.")
    cases = json.loads(Path("evaluation/cases.json").read_text())
    rubric = json.loads(Path("evaluation/assessments.json").read_text())
    rows = []
    latencies = []
    invalids = {"empty": b"", "utf8": b"\xff", "oversized": b"x" * 65537, "control": b"x\x00y"}
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "engineer"))
        if not user:
            raise SystemExit("Run the explicit development seed command first.")
        pg = db.scalar(text("SELECT version()")).split(" on ")[0]
        # Warm the connection and search index; report serial application-level timings, not network load.
        retrieve(db, user, "database")
        for case in cases:
            started = perf_counter()
            try:
                content = redact(
                    parse_log(invalids[case["invalid"]] if "invalid" in case else case["log"].encode())
                )
            except ValueError:
                rows.append(
                    {
                        "id": case["id"],
                        "expected": case["category"],
                        "actual": "invalid",
                        "correct": case["category"] == "invalid",
                    }
                )
                continue
            actual, _ = classify(content)
            docs = retrieve(db, user, actual)
            # Recall uses the labeled category to isolate retrieval from classification failures.
            oracle_docs = retrieve(db, user, case["category"]) if case["relevant"] else []
            report, _ = await investigate(db, user, content)
            elapsed = (perf_counter() - started) * 1000
            latencies.append(elapsed)
            accessible = {d.id: d for d in db.scalars(select(Document).where(allowed_documents(user)))}
            valid_citations = all(
                c["id"] in accessible
                and accessible[c["id"]].version == c["version"]
                and accessible[c["id"]].section == c["section"]
                for c in report["citations"]
            )
            valid_lines = all(o["text"] == content.splitlines()[o["line"] - 1] for o in report["observed"])
            supported = report["status"] == "supported"
            template = rubric["template_reviews"].get(actual, {})
            evidence_supported = (
                bool(
                    template.get("explanation_supported")
                    and template.get("checks_supported")
                    and actual == case["category"]
                )
                if supported
                else None
            )
            if case["id"] in rubric["case_overrides"]:
                evidence_supported = rubric["case_overrides"][case["id"]]["evidence_supported"]
            relevant = set(case["relevant"])
            rows.append(
                {
                    "id": case["id"],
                    "expected": case["category"],
                    "actual": actual,
                    "correct": actual == case["category"],
                    "status": report["status"],
                    "retrieved": [d.key for d in docs],
                    "recall_at_3": len(relevant & {d.key for d in oracle_docs}) / len(relevant)
                    if relevant
                    else None,
                    "end_to_end_hit": bool(relevant & {d.key for d in docs}) if relevant else None,
                    "citation_count": len(report["citations"]),
                    "citation_valid": valid_citations,
                    "log_references_valid": valid_lines,
                    "evidence_supported": evidence_supported,
                    "latency_ms": round(elapsed, 3),
                }
            )
    valid = [r for r in rows if r["expected"] != "invalid"]
    known = [r for r in valid if r["expected"] != "unknown"]
    unknown = [r for r in valid if r["expected"] == "unknown"]
    emitted = [r for r in valid if r["status"] == "supported"]
    ordered = sorted(latencies)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "conditions": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "postgres": pg,
            "mode": "baseline",
            "requests": "serial, warmed connection; timings include parse, two retrieval paths and analysis; exclude login, HTTP, browser and provider",
        },
        "cases": len(rows),
        "valid_logs": len(valid),
        "classification_accuracy": sum(r["correct"] for r in valid) / len(valid),
        "input_rejection": {
            "passed": sum(r["correct"] for r in rows if r["expected"] == "invalid"),
            "total": 4,
        },
        "retrieval_recall_at_3_oracle_category": statistics.mean(r["recall_at_3"] for r in known),
        "end_to_end_retrieval_hit_rate": sum(r["end_to_end_hit"] for r in known) / len(known),
        "citations": {
            "valid": sum(r["citation_count"] for r in valid if r["citation_valid"]),
            "total": sum(r["citation_count"] for r in valid),
        },
        "log_reference_validity": all(r["log_references_valid"] for r in valid),
        "evidence_support_author_rubric": {
            "supported": sum(r["evidence_supported"] for r in emitted),
            "emitted_reports": len(emitted),
        },
        "unknown_abstention": {
            "abstained": sum(r["status"] == "insufficient_evidence" for r in unknown),
            "total": len(unknown),
        },
        "known_abstention": {
            "abstained": sum(r["status"] == "insufficient_evidence" for r in known),
            "total": len(known),
        },
        "latency_ms": {
            "median": round(statistics.median(latencies), 3),
            "p95_nearest_rank": round(ordered[int(0.95 * len(ordered) + 0.999) - 1], 3),
            "max": round(max(latencies), 3),
        },
        "failures": [r["id"] for r in rows if not r["correct"]],
        "results": rows,
    }
    target = Path("evaluation/results.json")
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    asyncio.run(evaluate())
