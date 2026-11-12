import hashlib
import hmac
import logging
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session as DBSession

from app.analysis import insufficient, investigate
from app.config import settings
from app.db import get_db
from app.middleware import RequestLimitMiddleware
from app.models import Audit, Document, Incident, LoginAttempt, Session, User, now
from app.parsing import MAX_BYTES, parse_log
from app.redaction import redact
from app.security import (
    COOKIE,
    DUMMY_HASH,
    administrator,
    allowed_documents,
    check_origin,
    csrf_token,
    current_user,
    digest,
    document_for,
    incident_for,
    incident_scope,
    new_session,
    passwords,
)

app = FastAPI(title="IncidentLens", version="0.1.0", docs_url="/api/docs", redoc_url=None)
app.add_middleware(RequestLimitMiddleware)
root = Path(__file__).parent
app.mount("/static", StaticFiles(directory=root / "static"), name="static")
templates = Jinja2Templates(directory=root / "templates")
logger = logging.getLogger("incidentlens")


@app.middleware("http")
async def hardening(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if not request.url.path.startswith(("/api/docs", "/openapi.json")):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
    return response


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*")
    @classmethod
    def safe_text(cls, value):
        if isinstance(value, str) and any(ord(c) < 32 and c not in "\r\n\t" for c in value):
            raise ValueError("Unsupported control character")
        return value


class Login(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)


class Submission(Input):
    title: str = Field(min_length=3, max_length=160)
    log_text: str = Field(min_length=1, max_length=MAX_BYTES)


class Review(Input):
    decision: Literal["accepted", "rejected"]
    note: str = Field(default="", max_length=2000)


class DocumentInput(Input):
    key: str = Field(pattern=r"^[A-Z0-9-]{3,40}$")
    title: str = Field(min_length=3, max_length=160)
    section: str = Field(min_length=3, max_length=120)
    access: Literal["shared", "restricted"]
    content: str = Field(min_length=20, max_length=12000)
    active: bool = True


def audit(db, user, action, incident_id=None, details=None):
    db.add(Audit(actor_id=user.id, action=action, incident_id=incident_id, details=details or {}))


def user_view(user):
    return {"username": user.username, "role": user.role, "restricted_access": user.restricted_access}


@app.post("/api/auth/login")
def login(data: Login, request: Request, response: Response, db: DBSession = Depends(get_db)):
    check_origin(request)
    username = data.username.strip().lower()
    # Account-based throttling survives restarts and cannot be bypassed by rotating client IPs.
    subject = hmac.new(settings().session_secret.encode(), username.encode(), hashlib.sha256).hexdigest()
    cutoff = now() - timedelta(minutes=10)
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    attempts = db.scalar(
        select(func.count()).select_from(LoginAttempt).where(LoginAttempt.subject == subject)
    )
    if attempts >= 5:
        raise HTTPException(429, "Too many attempts; wait 10 minutes", headers={"Retry-After": "600"})
    user = db.scalar(select(User).where(User.username == username))
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.active:
        db.add(LoginAttempt(subject=subject))
        db.commit()  # Failed attempts must survive the HTTP exception rollback.
        raise HTTPException(401, "Invalid username or password")
    db.execute(delete(LoginAttempt).where(LoginAttempt.subject == subject))
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(Session).where(Session.token_hash == digest(old)))
    db.execute(delete(Session).where(Session.expires_at < now()))
    raw = new_session(db, user)
    audit(db, user, "signed_in")
    response.set_cookie(
        COOKIE,
        raw,
        httponly=True,
        secure=settings().session_secure,
        samesite="lax",
        max_age=8 * 3600,
        path="/",
    )
    return {"user": user_view(user), "csrf_token": csrf_token(raw)}


@app.get("/api/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"user": user_view(user), "csrf_token": csrf_token(request.cookies[COOKIE])}


@app.post("/api/auth/logout")
def logout(
    request: Request, response: Response, user: User = Depends(current_user), db: DBSession = Depends(get_db)
):
    db.execute(delete(Session).where(Session.token_hash == digest(request.cookies[COOKIE])))
    audit(db, user, "signed_out")
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    counts = dict(
        db.execute(
            select(Incident.review_state, func.count())
            .where(incident_scope(user))
            .group_by(Incident.review_state)
        ).all()
    )
    return {
        "total": sum(counts.values()),
        "pending": counts.get("pending", 0),
        "accepted": counts.get("accepted", 0),
        "rejected": counts.get("rejected", 0),
    }


@app.get("/api/incidents")
def history(
    user: User = Depends(current_user), db: DBSession = Depends(get_db), offset: int = 0, limit: int = 40
):
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, "Invalid pagination")
    rows = db.scalars(
        select(Incident)
        .where(incident_scope(user))
        .order_by(Incident.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        {"id": i.id, "title": i.title, "review_state": i.review_state, "created_at": i.created_at}
        for i in rows
    ]


async def create_incident(db, user, title, raw):
    if not 3 <= len(title.strip()) <= 160:
        raise HTTPException(422, "Title must contain 3–160 characters")
    try:
        # Keep storage and every later analysis stage on the same redacted, line-preserving input.
        log_text = redact(parse_log(raw))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    report, versions = await investigate(db, user, log_text)
    incident = Incident(
        owner_id=user.id,
        title=redact(title.strip()),
        log_text=log_text,
        report=report,
        source_versions=versions,
    )
    db.add(incident)
    db.flush()
    audit(db, user, "incident_created", incident.id, {"mode": report["mode"], "status": report["status"]})
    logger.info("incident_created id=%s mode=%s", incident.id, report["mode"])
    return {"id": incident.id}


@app.post("/api/incidents", status_code=201)
async def submit(data: Submission, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    return await create_incident(db, user, data.title, data.log_text.encode("utf-8"))


@app.post("/api/incidents/upload", status_code=201)
async def upload(
    title: str = Form(..., max_length=160),
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    try:
        raw = await file.read(MAX_BYTES + 1)
    finally:
        await file.close()
    return await create_incident(db, user, title, raw)


def visible_report(db, user, incident):
    if incident.source_versions:
        current = {
            d.id: d.version
            for d in db.scalars(
                select(Document).where(Document.id.in_(incident.source_versions), allowed_documents(user))
            )
        }
        if current != incident.source_versions:
            report = insufficient("Source access or version changed; submit a new investigation.")
            report["mode"] = "withheld"
            return report
    return incident.report


@app.get("/api/incidents/{incident_id}")
def detail(incident_id: str, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    i = incident_for(db, user, incident_id)
    return {
        "id": i.id,
        "title": i.title,
        "log_text": i.log_text,
        "report": visible_report(db, user, i),
        "review_state": i.review_state,
        "review_note": i.review_note,
        "created_at": i.created_at,
        "reviewed_at": i.reviewed_at,
    }


@app.post("/api/incidents/{incident_id}/review")
def review(
    incident_id: str, data: Review, user: User = Depends(current_user), db: DBSession = Depends(get_db)
):
    i = incident_for(db, user, incident_id)
    # Serialize concurrent review changes; audit is inserted in the same transaction.
    i = db.scalar(select(Incident).where(Incident.id == i.id).with_for_update())
    if visible_report(db, user, i)["status"] != "supported":
        raise HTTPException(409, "There is no supported recommendation to review")
    i.review_state, i.review_note, i.reviewed_at = data.decision, redact(data.note), now()
    audit(db, user, "recommendation_reviewed", i.id, {"decision": data.decision})
    return {"review_state": i.review_state}


@app.get("/api/incidents/{incident_id}/audit")
def incident_audit(incident_id: str, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    incident_for(db, user, incident_id)
    rows = db.execute(
        select(Audit, User.username)
        .join(User, User.id == Audit.actor_id)
        .where(Audit.incident_id == incident_id)
        .order_by(Audit.id)
    )
    return [
        {"actor": name, "action": a.action, "details": a.details, "created_at": a.created_at}
        for a, name in rows
    ]


def doc_view(d):
    return {
        "id": d.id,
        "key": d.key,
        "title": d.title,
        "section": d.section,
        "version": d.version,
        "access": d.access,
        "content": d.content,
        "active": d.active,
    }


@app.get("/api/documents")
def documents(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    query = select(Document).order_by(Document.key)
    if user.role != "admin":
        query = query.where(allowed_documents(user))
    return [doc_view(d) for d in db.scalars(query.limit(200))]


@app.get("/api/documents/{doc_id}")
def source(doc_id: str, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    return doc_view(document_for(db, user, doc_id))


@app.post("/api/documents", status_code=201)
def create_document(
    data: DocumentInput, user: User = Depends(administrator), db: DBSession = Depends(get_db)
):
    if db.scalar(select(Document.id).where(Document.key == data.key)):
        raise HTTPException(409, "Runbook key already exists")
    d = Document(**{k: redact(v) if isinstance(v, str) else v for k, v in data.model_dump().items()})
    db.add(d)
    db.flush()
    audit(db, user, "document_created", details={"document_id": d.id, "version": d.version})
    return doc_view(d)


@app.put("/api/documents/{doc_id}")
def update_document(
    doc_id: str, data: DocumentInput, user: User = Depends(administrator), db: DBSession = Depends(get_db)
):
    d = db.scalar(select(Document).where(Document.id == doc_id).with_for_update())
    if not d:
        raise HTTPException(404, "Document not found")
    if db.scalar(select(Document.id).where(Document.key == data.key, Document.id != d.id)):
        raise HTTPException(409, "Runbook key already exists")
    for k, v in data.model_dump().items():
        setattr(d, k, redact(v) if isinstance(v, str) else v)
    d.version += 1
    audit(db, user, "document_updated", details={"document_id": d.id, "version": d.version})
    db.flush()
    return doc_view(d)


@app.get("/api/admin/audit")
def admin_audit(user: User = Depends(administrator), db: DBSession = Depends(get_db)):
    return [
        {"action": a.action, "actor": name, "details": a.details, "created_at": a.created_at}
        for a, name in db.execute(
            select(Audit, User.username)
            .join(User, User.id == Audit.actor_id)
            .order_by(Audit.id.desc())
            .limit(100)
        )
    ]


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: DBSession = Depends(get_db)):
    try:
        db.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
    except Exception as exc:
        raise HTTPException(503, "Database unavailable or migrations missing") from exc
    return {"status": "ready"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")
