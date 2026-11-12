from sqlalchemy import select

from app.models import Incident, Session, User
from tests.conftest import sign_in

LOG = "INFO checkout started\nERROR postgres connection refused at db:5432\nWARN request failed"


def create(client, log=LOG):
    response = client.post("/api/incidents", json={"title": "Synthetic checkout failure", "log_text": log})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_end_to_end_persistence_and_audit(engineer, db):
    id = create(engineer)
    db.expire_all()
    stored = db.get(Incident, id)
    assert stored.log_text == LOG
    report = engineer.get(f"/api/incidents/{id}").json()["report"]
    assert report["mode"] == "baseline" and report["status"] == "supported"
    assert report["observed"][0]["line"] == 2
    assert report["citations"] and report["provider"] is None
    for citation in report["citations"]:
        source = engineer.get("/api/documents/" + citation["id"])
        assert source.status_code == 200
        assert source.json()["section"] == citation["section"]
        assert source.json()["version"] == citation["version"]
    result = engineer.post(
        f"/api/incidents/{id}/review",
        json={"decision": "accepted", "note": "Monitoring confirms a listener issue"},
    )
    assert result.status_code == 200
    detail = engineer.get(f"/api/incidents/{id}").json()
    assert detail["review_state"] == "accepted" and detail["reviewed_at"]
    audit = engineer.get(f"/api/incidents/{id}/audit").json()
    assert [a["action"] for a in audit] == ["incident_created", "recommendation_reviewed"]
    assert engineer.get("/api/dashboard").json()["accepted"] == 1
    assert any(i["id"] == id for i in engineer.get("/api/incidents").json())


def test_unknown_cannot_be_accepted(engineer):
    id = create(engineer, "INFO everything looks normal")
    assert engineer.get(f"/api/incidents/{id}").json()["report"]["status"] == "insufficient_evidence"
    assert engineer.post(f"/api/incidents/{id}/review", json={"decision": "accepted"}).status_code == 409


def test_log_upload_and_validation(engineer):
    response = engineer.post(
        "/api/incidents/upload",
        data={"title": "Uploaded incident"},
        files={"file": ("sample.log", LOG.encode(), "text/plain")},
    )
    assert response.status_code == 201
    for raw in [b"\xff", b"a\0b", b"x" * 65537]:
        assert (
            engineer.post(
                "/api/incidents/upload", data={"title": "Bad file"}, files={"file": ("bad.log", raw)}
            ).status_code
            == 422
        )
    assert engineer.post("/api/incidents", json={"title": "Big", "log_text": "x" * 90000}).status_code == 413
    assert engineer.post("/api/incidents", json={"title": "   ", "log_text": LOG}).status_code == 422


def test_secrets_redacted_at_rest_and_in_notes(engineer, db):
    id = create(engineer, LOG + "\npassword=super-sensitive-value")
    engineer.post(f"/api/incidents/{id}/review", json={"decision": "rejected", "note": "token=review-secret"})
    db.expire_all()
    stored = db.get(Incident, id)
    assert "super-sensitive-value" not in stored.log_text
    assert "review-secret" not in stored.review_note


def test_session_logout_and_security_headers(client, db):
    response = sign_in(client)
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=lax" in response.headers["set-cookie"]
    raw = client.cookies.get("incidentlens_session")
    stored = db.scalar(select(Session))
    assert raw != stored.token_hash
    assert client.get("/").headers["content-security-policy"].startswith("default-src 'self'")
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert not db.get(Session, stored.token_hash)


def test_expired_and_disabled_sessions(engineer, db):
    from datetime import timedelta

    from app.models import now

    session = db.scalar(select(Session))
    session.expires_at = now() - timedelta(seconds=1)
    db.flush()
    assert engineer.get("/api/incidents").status_code == 401
    sign_in(engineer)
    user = db.scalar(select(User).where(User.username == "engineer"))
    user.active = False
    db.flush()
    assert engineer.get("/api/documents").status_code == 401


def test_login_throttle_and_origin(client):
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "engineer", "password": "bad"},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    for _ in range(5):
        assert (
            client.post("/api/auth/login", json={"username": "absent", "password": "bad"}).status_code == 401
        )
    assert client.post("/api/auth/login", json={"username": "absent", "password": "bad"}).status_code == 429


def test_csrf(engineer):
    assert (
        engineer.post(
            "/api/incidents",
            json={"title": "Malformed CSRF", "log_text": LOG},
            headers={b"x-csrf-token": b"\xff"},
        ).status_code
        == 403
    )
    assert (
        engineer.post(
            "/api/incidents", json={"title": "Bad request", "log_text": LOG}, headers={"X-CSRF-Token": "bad"}
        ).status_code
        == 403
    )
    assert (
        engineer.post(
            "/api/incidents",
            json={"title": "Bad request", "log_text": LOG},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )


def test_health_and_pagination(client):
    assert client.get("/health/ready").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/incidents").status_code == 401
    sign_in(client)
    assert client.get("/api/incidents?offset=-1").status_code == 422


def test_control_characters_in_metadata_are_rejected(engineer):
    assert engineer.post("/api/incidents", json={"title": "Bad\x00title", "log_text": LOG}).status_code == 422
    id = create(engineer)
    assert (
        engineer.post(
            f"/api/incidents/{id}/review", json={"decision": "accepted", "note": "Bad\x00note"}
        ).status_code
        == 422
    )
