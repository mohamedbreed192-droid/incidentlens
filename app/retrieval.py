from sqlalchemy import func, select

from app.models import Document
from app.security import allowed_documents

QUERIES = {
    "database": "database OR postgres OR connection",
    "credentials": "credential OR token OR authentication",
    "service": "upstream OR unavailable OR health",
}


def retrieve(db, user, category, limit=3):
    if category not in QUERIES:
        return []
    query = func.websearch_to_tsquery("english", QUERIES[category])
    # Authorization is part of the SQL query, before materialization or provider input.
    return list(
        db.scalars(
            select(Document)
            .where(allowed_documents(user), Document.search_vector.op("@@")(query))
            .order_by(func.ts_rank_cd(Document.search_vector, query).desc(), Document.key)
            .limit(limit)
        )
    )
