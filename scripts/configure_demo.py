"""Generate local-only configuration with random secrets; refuse to overwrite existing .env."""

import secrets
from pathlib import Path

target = Path(".env")
if target.exists():
    raise SystemExit(".env already exists; preserve it and edit explicitly if needed.")
password = secrets.token_hex(24)
target.touch(mode=0o600, exist_ok=False)
target.write_text(
    f"POSTGRES_PASSWORD={password}\n"
    f"DATABASE_URL=postgresql+psycopg://incidentlens:{password}@db:5432/incidentlens\n"
    f"SESSION_SECRET={secrets.token_hex(32)}\nAPP_ENV=development\nSESSION_SECURE=false\n"
    "ALLOWED_ORIGIN=http://localhost:8000\nANALYSIS_MODE=baseline\nOPENAI_API_KEY=\n"
    "OPENAI_MODEL=gpt-4.1-mini\nPROVIDER_TIMEOUT=12\n"
)
print("Created .env with random local secrets. Run docker compose up --build -d.")
