from time import perf_counter

from app.config import settings
from app.parsing import classify
from app.providers import OpenAIProvider, ProviderError
from app.reports import Check, Explanation, ProviderReport, validate_grounding
from app.retrieval import retrieve

GUIDANCE = {
    "database": (
        "DB-001",
        "The application could not obtain a database connection. Network reachability, the database listener, or connection capacity may explain this observation.",
        [
            "Compare the configured database hostname and port with the approved inventory.",
            "Inspect database listener health and current connection capacity through approved monitoring.",
        ],
    ),
    "credentials": (
        "AUTH-001",
        "The log indicates rejected or expired authentication material. Credential validity or rotation timing may explain the failure.",
        [
            "Check expiry and issuer metadata without copying the credential value.",
            "Compare the deployed credential reference with the approved rotation record.",
        ],
    ),
    "service": (
        "SVC-001",
        "The application reported an unavailable upstream service. Service health, routing, or a recent deployment may explain this observation.",
        [
            "Inspect upstream health and endpoint registration in approved monitoring.",
            "Compare the failure timestamp with deployment and routing change records.",
        ],
    ),
}


def insufficient(reason, category="unknown", observed=None):
    return {
        "status": "insufficient_evidence",
        "category": category,
        "reason": reason,
        "mode": "baseline",
        "provider": None,
        "model": None,
        "observed": observed or [],
        "explanations": [],
        "checks": [],
        "citations": [],
    }


async def investigate(db, user, text):
    started = perf_counter()
    category, lines = classify(text)
    observed = [{"line": n, "text": text.splitlines()[n - 1]} for n in lines]
    if category == "unknown":
        result = insufficient("Unknown or conflicting signals; obtain more context.", observed=observed)
        docs = []
    else:
        docs = retrieve(db, user, category)
        key, explanation, checks = GUIDANCE[category]
        supporting = next((d for d in docs if d.key == key), None)
        if not supporting or not all(
            check.casefold().rstrip(".") in supporting.content.casefold() for check in checks
        ):
            result = insufficient("No accessible supported runbook was retrieved.", category, observed)
        else:
            baseline = ProviderReport(
                category=category,
                explanations=[Explanation(text=explanation, log_lines=lines, source_ids=[supporting.id])],
                checks=[Check(text=c, source_ids=[supporting.id]) for c in checks],
            )
            output = baseline
            mode, provider, model, fallback = "baseline", None, None, None
            if settings().analysis_mode == "openai":
                try:
                    payload = {
                        "category": category,
                        "observed": observed,
                        "runbooks": [
                            {
                                "id": d.id,
                                "title": d.title,
                                "section": d.section,
                                "version": d.version,
                                "content": d.content,
                            }
                            for d in docs
                        ],
                    }
                    output = validate_grounding(
                        await OpenAIProvider(settings()).investigate(payload), category, lines, docs
                    )
                    mode, provider, model = "model_assisted", "OpenAI", settings().openai_model
                except (ProviderError, ValueError) as exc:
                    fallback = str(exc) if isinstance(exc, ProviderError) else "provider_invalid_references"
            used = {sid for item in [*output.explanations, *output.checks] for sid in item.source_ids}
            result = {
                "status": "supported",
                "category": category,
                "reason": None,
                "observed": observed,
                "mode": mode,
                "provider": provider,
                "model": model,
                "fallback_reason": fallback,
                "explanations": [x.model_dump() for x in output.explanations],
                "checks": [x.model_dump() for x in output.checks],
                "citations": [
                    {"id": d.id, "key": d.key, "title": d.title, "section": d.section, "version": d.version}
                    for d in docs
                    if d.id in used
                ],
            }
    result["latency_ms"] = round((perf_counter() - started) * 1000, 2)
    # Protect all model context, even a source not explicitly cited in its response.
    return result, {d.id: d.version for d in docs}
