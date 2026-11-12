import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.analysis import investigate
from app.config import Settings, settings
from app.models import Document, User
from app.providers import OpenAIProvider, ProviderError
from app.reports import ProviderReport, validate_grounding


def valid_response(doc_id="source-1"):
    return {
        "category": "database",
        "explanations": [
            {"text": "A listener issue may explain this failure.", "log_lines": [2], "source_ids": [doc_id]}
        ],
        "checks": [{"text": "Inspect listener health.", "source_ids": [doc_id]}],
    }


def config():
    return Settings(
        database_url="postgresql+psycopg://unused/test",
        session_secret="test-only-secret-with-more-than-32-characters",
        openai_api_key="synthetic-key-not-live",
    )


def test_real_adapter_request_shape_redaction_and_output_validation():
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["messages"][0]["role"] == "system"
        assert "UNTRUSTED DATA" in body["messages"][0]["content"]
        assert "not-for-provider" not in request.content.decode()
        assert "[REDACTED]" in request.content.decode()
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(valid_response())}}]})

    adapter = OpenAIProvider(config(), httpx.MockTransport(handler))
    result = asyncio.run(adapter.investigate({"log": "password=not-for-provider"}))
    assert result.category == "database"


@pytest.mark.parametrize(
    "status,code",
    [(429, "provider_rate_limited"), (503, "provider_unavailable"), (401, "provider_unavailable")],
)
def test_provider_http_failures(status, code):
    adapter = OpenAIProvider(
        config(),
        httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": "sensitive provider text"})
        ),
    )
    with pytest.raises(ProviderError, match=code):
        asyncio.run(adapter.investigate({}))


def test_provider_timeout():
    def handler(request):
        raise httpx.ReadTimeout("private timeout context")

    with pytest.raises(ProviderError, match="provider_timeout"):
        asyncio.run(OpenAIProvider(config(), httpx.MockTransport(handler)).investigate({}))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {"content": "not json"}}]},
        {"choices": [{"message": {"content": '{"category":"database","invented":"bad"}'}}]},
    ],
)
def test_malformed_provider_responses(payload):
    adapter = OpenAIProvider(config(), httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    with pytest.raises(ProviderError):
        asyncio.run(adapter.investigate({}))


def test_structured_references_and_extra_fields_rejected():
    from types import SimpleNamespace

    data = valid_response()
    with pytest.raises(ValueError):
        validate_grounding(
            ProviderReport.model_validate(data), "database", [1], [SimpleNamespace(id="source-1")]
        )
    with pytest.raises(ValueError):
        validate_grounding(
            ProviderReport.model_validate(data), "database", [2], [SimpleNamespace(id="restricted")]
        )
    data["command"] = "delete everything"
    with pytest.raises(ValidationError):
        ProviderReport.model_validate(data)


def test_provider_not_configured_is_explicit():
    conf = config()
    conf.openai_api_key = ""
    with pytest.raises(ProviderError, match="provider_not_configured"):
        asyncio.run(OpenAIProvider(conf).investigate({}))


def test_pipeline_excludes_restricted_sources_and_falls_back(db, monkeypatch):
    user = db.scalar(select(User).where(User.username == "engineer"))
    restricted = db.scalar(select(Document).where(Document.key == "DB-PRIVATE"))

    async def fail(self, payload):
        assert restricted.id not in {d["id"] for d in payload["runbooks"]}
        raise ProviderError("provider_timeout")

    monkeypatch.setattr(settings(), "analysis_mode", "openai")
    monkeypatch.setattr(OpenAIProvider, "investigate", fail)
    report, _ = asyncio.run(investigate(db, user, "INFO starting\npostgres connection refused"))
    assert report["mode"] == "baseline" and report["fallback_reason"] == "provider_timeout"


def test_pipeline_success_and_hallucination_fallback(db, monkeypatch):
    user = db.scalar(select(User).where(User.username == "engineer"))

    async def good(self, payload):
        id = next(d["id"] for d in payload["runbooks"] if d["title"] == "Database connection failures")
        return ProviderReport.model_validate(valid_response(id))

    monkeypatch.setattr(settings(), "analysis_mode", "openai")
    monkeypatch.setattr(OpenAIProvider, "investigate", good)
    report, _ = asyncio.run(investigate(db, user, "INFO start\npostgres connection refused"))
    assert report["mode"] == "model_assisted" and report["provider"] == "OpenAI"

    async def bad(self, payload):
        return ProviderReport.model_validate(valid_response("unavailable-source"))

    monkeypatch.setattr(OpenAIProvider, "investigate", bad)
    report, _ = asyncio.run(investigate(db, user, "INFO start\npostgres connection refused"))
    assert report["mode"] == "baseline" and report["fallback_reason"] == "provider_invalid_references"
