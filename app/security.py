import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import get_db
from app.models import Document, Incident, Session, User, now

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("synthetic-unused-password")
COOKIE = "incidentlens_session"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(raw):
    return hmac.new(settings().session_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def check_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin != settings().allowed_origin:
        raise HTTPException(403, "Origin not allowed")


def current_user(request: Request, db: DBSession = Depends(get_db)):
    raw = request.cookies.get(COOKIE, "")
    session = db.get(Session, digest(raw)) if raw else None
    user = db.get(User, session.user_id) if session and session.expires_at > now() else None
    if not user or not user.active:
        raise HTTPException(401, "Sign in to continue")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        if not hmac.compare_digest(
            request.headers.get("x-csrf-token", "").encode(), csrf_token(raw).encode()
        ):
            raise HTTPException(403, "Invalid CSRF token; refresh and retry")
    return user


def administrator(user: User = Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def allowed_documents(user):
    if user.role == "admin" or user.restricted_access:
        return Document.active.is_(True)
    return (Document.active.is_(True)) & (Document.access == "shared")


def document_for(db, user, doc_id):
    doc = db.scalar(select(Document).where(Document.id == doc_id, allowed_documents(user)))
    if not doc:
        raise HTTPException(404, "Source not found or unavailable")
    return doc


def incident_for(db, user, incident_id):
    query = select(Incident).where(Incident.id == incident_id)
    if user.role != "admin":
        query = query.where(Incident.owner_id == user.id)
    incident = db.scalar(query)
    if not incident:
        raise HTTPException(404, "Incident not found or unavailable")
    return incident


def incident_scope(user):
    return or_(Incident.owner_id == user.id, user.role == "admin")


def new_session(db, user):
    raw = secrets.token_urlsafe(32)
    db.add(Session(token_hash=digest(raw), user_id=user.id, expires_at=now() + timedelta(hours=8)))
    return raw
