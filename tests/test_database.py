import uuid

from sqlalchemy import delete, inspect, select, text
from sqlalchemy.orm import Session

from alembic import command
from alembic.config import Config
from app.db import engine
from app.models import User


def test_migrated_schema_matches_metadata():
    command.check(Config("alembic.ini"))
    inspector = inspect(engine)
    assert {"users", "sessions", "documents", "incidents", "audit", "login_attempts"} <= set(
        inspector.get_table_names()
    )
    index = next(i for i in inspector.get_indexes("documents") if i["name"] == "ix_documents_search")
    assert index["dialect_options"]["postgresql_using"] == "gin"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))


def test_committed_data_visible_on_new_connection():
    name = "persistence-" + uuid.uuid4().hex[:10]
    with Session(engine) as first:
        row = User(username=name, password_hash="test-placeholder-not-a-login", role="engineer")
        first.add(row)
        first.commit()
        id = row.id
    try:
        with Session(engine) as second:
            assert second.scalar(select(User.username).where(User.id == id)) == name
    finally:
        with engine.begin() as connection:
            connection.execute(delete(User).where(User.id == id))
