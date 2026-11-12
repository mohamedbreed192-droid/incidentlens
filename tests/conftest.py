import os

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config

local = dotenv_values(".env")
url = os.environ.get("TEST_DATABASE_URL")
if not url:
    source = make_url(local.get("DATABASE_URL", "postgresql+psycopg://localhost/incidentlens"))
    url = source.set(host="127.0.0.1", port=55432, database="incidentlens_test").render_as_string(
        hide_password=False
    )
if "test" not in make_url(url).database:
    raise RuntimeError("Tests require a dedicated database with 'test' in its name")
os.environ.update(
    DATABASE_URL=url,
    SESSION_SECRET="synthetic-test-session-secret-32-characters",
    APP_ENV="test",
    SESSION_SECURE="false",
    ALLOWED_ORIGIN="http://testserver",
    ANALYSIS_MODE="baseline",
    OPENAI_API_KEY="",
)

from app.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

DEMO_PASSWORD = "Synthetic-tests-only-42!"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    command.upgrade(Config("alembic.ini"), "head")
    with Session(engine) as db:
        seed(db, DEMO_PASSWORD)
        db.commit()


@pytest.fixture
def db(migrated_database):
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(db):
    def override():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def sign_in(client, username="engineer"):
    result = client.post("/api/auth/login", json={"username": username, "password": DEMO_PASSWORD})
    assert result.status_code == 200, result.text
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result


@pytest.fixture
def engineer(client):
    sign_in(client)
    return client
