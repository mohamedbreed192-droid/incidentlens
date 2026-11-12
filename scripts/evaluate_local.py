"""Evaluate the Compose demo from the host, without printing local secrets or calling a provider."""

import asyncio
import os

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def main():
    config = dotenv_values(".env")
    if not config.get("DATABASE_URL") or not config.get("SESSION_SECRET"):
        raise SystemExit("Generate the local demo .env and start/seed Compose first.")
    url = make_url(config["DATABASE_URL"]).set(host="127.0.0.1", port=55432)
    os.environ.update(
        DATABASE_URL=url.render_as_string(hide_password=False),
        SESSION_SECRET=config["SESSION_SECRET"],
        ANALYSIS_MODE="baseline",
    )
    from scripts.evaluate import evaluate

    asyncio.run(evaluate())


if __name__ == "__main__":
    main()
