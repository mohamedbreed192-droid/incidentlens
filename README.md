# IncidentLens

[![CI](https://github.com/mohamedbreed192-droid/incidentlens/actions/workflows/ci.yml/badge.svg)](https://github.com/mohamedbreed192-droid/incidentlens/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-28563f.svg)](LICENSE)

**Turn a short application log into an inspectable incident investigation.**

IncidentLens helps an IT engineer collect failure signals, retrieve permitted troubleshooting sections, and review a proposed investigation direction. It distinguishes observed log lines from suggested explanations and cited guidance. Unknown or conflicting signals produce an explicit insufficient-evidence report.

Built by **Mohamed Said**, a Computer Science student at Canadian University Dubai. This is a **student portfolio prototype using synthetic data** from fictional Northstar Labs. It is not production-ready, connected to real infrastructure, or affiliated with IBM. It never executes commands, changes infrastructure, or remediates incidents.

![Real desktop screenshot of an investigation, with observed evidence, cited guidance, review, and activity history](docs/screenshots/desktop-investigation.png)

## What works

- Server-side sign-in with Argon2 password hashes, expiring opaque sessions, CSRF checks, and administrator/engineer roles.
- Bounded UTF-8 log upload or paste, input validation, common-secret redaction, and line-preserving evidence extraction.
- Three initial patterns: database connection failures, expired/invalid credentials, and unavailable services. Multiple categories and unfamiliar signals abstain.
- PostgreSQL full-text retrieval with document authorization in the SQL query **before** any result enters model context.
- Reports with actual log line numbers, inspectable document sections and versions, diagnostic checks, mode/provider provenance, and explicit abstention.
- Incident history, real database-derived dashboard counts, accept/reject decisions, review notes, and application audit history.
- Administrator document creation, editing, version increments, access selection, archiving, and recent audit inspection.
- A deterministic baseline that needs no model credentials, plus a real, opt-in OpenAI HTTPS adapter with schema/reference validation and fallback handling.
- Responsive HTML/CSS/JavaScript interface, Docker Compose, Alembic migrations, PostgreSQL integration tests, browser checks, and GitHub Actions.

The baseline uses reviewed category templates, not a language model. The interface identifies it as **Deterministic baseline**. Provider adapter tests use mocks; live model behavior has not been verified and no model charges were incurred.

## Start the local demo

Requirements: Git, Python 3.12+, and Docker Engine/Desktop with Compose v2. Port 8000 and local database port 55432 must be free.

```bash
git clone https://github.com/mohamedbreed192-droid/incidentlens.git
cd incidentlens
python3 scripts/configure_demo.py
docker compose up --build -d
docker compose exec app python -m app.seed --demo
```

The configuration script creates an ignored `.env` with random session/database secrets and refuses to overwrite an existing file. The explicit seed command asks you to **choose a local demo password** of 12–128 characters. It creates missing accounts and synthetic runbooks; it does not change an existing account's password. There are no automatically enabled default credentials.

Open **http://localhost:8000** and sign in with `engineer` and the password you chose. The other demo usernames are `analyst` and `admin`, with that same local demo password on first creation.

| Demo account | Access |
| --- | --- |
| `engineer` | Own incidents and shared active runbooks |
| `analyst` | Own incidents, shared and restricted active runbooks |
| `admin` | All incidents, runbook management, and administrative audit records |

These are explicitly synthetic development accounts. `APP_ENV=production` disables the seed command and requires an HTTPS origin and secure cookies. Production identity lifecycle, password recovery, and hardened hosting are not implemented.

Useful commands:

```bash
docker compose ps
curl http://localhost:8000/health/ready
docker compose logs app
docker compose down  # preserves the local database volume
```

Both application and database ports bind to loopback. Compose waits for database health, runs migrations as a one-shot service, and then starts the non-root application container. `/health/live` checks the process; `/health/ready` checks database access and the migration-version table. Runbook seeding never happens during application startup.

For manual configuration, copy [.env.example](.env.example), replace both placeholder secrets, and keep the database password consistent with `DATABASE_URL`. Use `.env` for local values only. Change `ALLOWED_ORIGIN` if the browser origin changes. HTTP sessions work locally because the generated configuration explicitly sets `SESSION_SECURE=false`.

## Five-minute walkthrough

1. Sign in as `engineer`. An empty database shows an empty history and zero counts.
2. Open **New incident**, set a title, and paste [database.log](fixtures/development/database.log) or upload it.
3. Inspect **L2** under observed evidence, the tentative explanation, and the **DB-001** source button. The source dialog displays the actual section and version as inert text.
4. Add a review note and accept or reject the recommendation. The persisted decision and actor/timestamp appear in activity history.
5. Submit [unknown.log](fixtures/development/unknown.log). It produces insufficient evidence and cannot be accepted as a supported recommendation.
6. Inspect the knowledge library. The ordinary engineer cannot see the restricted topology runbook, including by direct ID.
7. Sign out, then sign in as `admin` to create, edit, or archive a runbook section. Each edit increments its version. Earlier reports depending on changed or inaccessible sources are withheld rather than exposing stale context.

![Actual dashboard with database-derived counts](docs/screenshots/desktop-dashboard.png)

<details>
<summary>More real application screenshots</summary>

![Real source-inspection dialog](docs/screenshots/desktop-source.png)
![Real knowledge library](docs/screenshots/desktop-library.png)
![Real insufficient-evidence state](docs/screenshots/desktop-insufficient.png)
<img src="docs/screenshots/mobile-investigation.png" alt="Actual investigation on a 390-pixel mobile viewport" width="390">

Screenshots were captured by [the browser workflow](scripts/browser_check.py) against the running Docker application with synthetic submissions. The counts reflect those submissions; fresh installations start at zero.

</details>

## Architecture and choices

```mermaid
flowchart LR
    U[Engineer / administrator] --> UI[HTML + CSS + JavaScript]
    UI --> API[FastAPI endpoints]
    API --> AUTH[Session + CSRF + authorization]
    AUTH --> P[Validate, redact, parse]
    P --> RET[Permission-filtered full-text retrieval]
    RET --> BASE[Deterministic analysis]
    RET -. explicit opt-in .-> MODEL[Provider interface / OpenAI adapter]
    MODEL --> VAL[Schema + reference validation]
    VAL --> REPORT[Report or labeled baseline fallback]
    BASE --> REPORT
    AUTH --> DB[(PostgreSQL)]
    RET --> DB
    REPORT --> DB
    API --> REVIEW[Human review + audit transaction]
    REVIEW --> DB
```

This is a **modular monolith**: one application and one database. `parsing.py`, `redaction.py`, `retrieval.py`, `analysis.py`, `providers.py`, and `security.py` separate the boundaries that need independent tests. There are no queues, agent frameworks, microservices, or autonomous tools.

| Technology | Purpose and tradeoff |
| --- | --- |
| FastAPI + Pydantic | Python HTTP endpoints and validated request/model shapes; easier to explain than a distributed stack |
| PostgreSQL | Durable relational state, JSONB reports, transactions, and retrieval in one service |
| SQLAlchemy | Parameterized database queries and explicit relationships/transactions |
| Alembic | Versioned schema migrations; not `create_all` at startup |
| Full-text search | Generated English `tsvector`, GIN index, `websearch_to_tsquery`, deterministic rank/key ordering; lexical rather than semantic |
| Vanilla HTML/CSS/JS | Functional responsive interface without a frontend framework or build chain |
| pwdlib + Argon2 | Maintained password-hashing interface and memory-hard password hashing |
| httpx | Small, mockable real provider adapter with bounded timeouts |
| pytest + Playwright | Real PostgreSQL authorization/workflow tests and actual browser behavior |

The three supported baseline templates require the corresponding retrieved core runbook and the diagnostic-check text it supports. Removing that guidance causes abstention. Adding arbitrary runbooks does not automatically create new baseline categories. See [engineering decisions](docs/DECISIONS.md) and [retrieval/model design](docs/MODELS.md).

## Permission model

Engineers can list, open, and review only their own incidents. Administrators can inspect all incidents. Runbooks have `shared` or `restricted` access and an active/archive state; only administrators or explicitly cleared engineers can retrieve restricted sections. The demo seed defines the users' roles and clearance; user administration is not a UI feature.

Authorization applies to backend queries, direct source IDs, incident IDs, review endpoints, and audit endpoints. Unknown and inaccessible resources return the same 404 message. Saved reports track **every retrieved context document's version**, including model inputs not explicitly cited. If any source is archived, changes version, or becomes inaccessible, the full report is withheld. Logs and incident titles remain visible to their owner/admin. Audit metadata contains action and decision records, not hidden document text or prior review notes.

Opaque session cookies are HttpOnly and SameSite=Lax; the database stores only token hashes. State-changing authenticated requests require a session-bound CSRF header and check the browser origin when supplied. Account-based login throttling is persisted. These controls are a prototype design, not a security guarantee. Read the [threat model](docs/THREAT_MODEL.md).

## Actual evaluation and verification

The frozen [evaluation cases](evaluation/cases.json) contain **40 synthetic cases**: 24 known-category logs, 12 unknown/ambiguous logs, and 4 malformed inputs. Development walkthrough files are separate. Both sets were written by the project author; this is not an independently held-out enterprise benchmark.

| Measurement | Recorded local result |
| --- | --- |
| Classification accuracy, valid logs only | **32/36 (88.9%)** |
| Recall@3, given the labeled category | **24/24 (100%)** |
| End-to-end retrieval hit, including classification | **21/24 (87.5%)** |
| Citation ID, version, section, and current accessibility | **22/22 valid** |
| Observed line number/text references | All emitted references matched the supplied redacted log |
| Evidence support, author-reviewed template rubric plus label agreement | **21/22 emitted reports** |
| Unknown/ambiguous cases producing insufficient evidence | **11/12** |
| Known-category cases incorrectly abstaining | **3/24** |
| Malformed input rejection | **4/4** |
| Local serial analysis/evaluation timing | **4.591 ms median; 9.003 ms p95; 12.625 ms maximum** |
| Authenticated incident-creation HTTP latency, 36/36 successful requests | **8.939 ms median; 12.500 ms p95; 50.636 ms maximum** |
| Backend tests | **49 passed**, **94% statement coverage** in the recorded local run |

Timings use Python 3.12.14, PostgreSQL 16.15, and Linux x86-64 in the managed development environment with a warm connection. They include parsing, analysis, and extra retrieval measurement queries; they exclude HTTP, authentication, browser rendering, external models, and load/concurrency testing. They are not production latency claims.

A separate [HTTP benchmark](evaluation/http-results.json) measured 36 authenticated, serial `POST /api/incidents` requests over loopback to the running Docker application. It includes request validation, analysis, incident/audit persistence, commit, and response transport, with a warm app/database and no concurrent load. Login, verification reads, browser rendering, cold starts, and models are excluded. The maximum is retained rather than hidden. Reproduce it with `python -m scripts.benchmark_http`; it prompts for the local demo password and creates synthetic records.

**Failures are retained:** `DB08`, `AU08`, and `SV08` use unsupported wording and abstain. `UN10` explicitly quotes a training example but is incorrectly classified as a real database failure. The classifier does not understand negation or event context. A valid citation does **not** establish that an incident-specific explanation is true.

The [evaluation report](docs/EVALUATION.md) defines the denominators, source-support rubric, restrictions, injection checks, and limitations. [Raw results](evaluation/results.json) include per-case predictions, failures, and timing conditions. GitHub Actions runs PostgreSQL tests, the same evaluation, and desktop/mobile browser checks; each run uploads verification artifacts.

## Run checks yourself

The running Compose database exposes loopback port 55432 for host-side development. Use a separate database whose name contains `test`; the test harness refuses other names.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.lock
docker compose up -d db
docker compose exec db createdb -U incidentlens incidentlens_test
python -m pytest --cov=app --cov-report=term-missing
ruff check app tests scripts alembic
ruff format --check app tests scripts alembic
node --check app/static/app.js
```

The local test harness derives the test database connection from `.env`, substitutes `127.0.0.1:55432`, and applies Alembic migrations. Set `TEST_DATABASE_URL` explicitly for another PostgreSQL installation. Tests use transactions/savepoints and verify a committed row from a second connection. They never substitute SQLite for PostgreSQL.

To rerun evaluation against the migrated/seeded Compose demo from the host:

```bash
python -m scripts.evaluate_local
```

This helper reads the ignored local `.env`, selects the loopback database port, and forces baseline mode without displaying secrets. It updates `evaluation/results.json` with the new run. For another installation, configure `DATABASE_URL`, `SESSION_SECRET`, and `ANALYSIS_MODE=baseline` in your environment and run `python -m scripts.evaluate`.

For browser verification against the running demo:

```bash
python -m playwright install chromium
python -m scripts.browser_check
# Prompts for the local engineer password. For an installed system browser:
python -m scripts.browser_check --chromium /usr/bin/chromium
```

The browser script checks desktop (1440×1000) and mobile (390×844), sign-in, submission, evidence, source inspection, keyboard dialog dismissal, review/audit, history, permitted library, API denial, unknown-log upload, overflow, and sign-out. Artifacts go to ignored `test-results/`. Use only synthetic demo instances: it deliberately creates incidents and review records.

## Optional model integration

The application works fully in `ANALYSIS_MODE=baseline`. A maintainer can opt into `ANALYSIS_MODE=openai` and configure `OPENAI_API_KEY`, `OPENAI_MODEL`, and `PROVIDER_TIMEOUT` in their local environment, then recreate the app container. Provider use can incur charges; **this project did not make live paid calls**. No credentials are needed for tests.

The adapter calls OpenAI's real chat-completions endpoint with a JSON schema, no tools, an output-token bound, and a timeout. Logs and runbooks are untrusted user data. The application redacts common secrets before persistence/provider input and validates returned shapes, categories, line references, and source IDs. Timeouts, rate limits, unavailable service, malformed JSON, or invalid references produce a clearly labeled baseline fallback. These checks cannot prove factual correctness or eliminate prompt injection.

[Model documentation](docs/MODELS.md) explains the provider interface, mocked checks, unverified live behavior, and a practical extension path for IBM watsonx or a local Granite model. No IBM adapter or semantic retrieval is claimed as implemented.

## Limits and next work

- English lexical rules and a six-section synthetic corpus; missed wording, quoted examples, and negation are known failure modes.
- Source support is assessed through a small author-reviewed rubric; no independent expert, real incident, or live-model benchmark.
- Secret redaction covers common patterns, not arbitrary secrets, personal data, or adversarial encodings. Do not submit sensitive logs.
- One fictional organization, own-incident access and one restricted clearance flag; no SSO, password recovery, user provisioning UI, tenant isolation, or granular grants.
- Audit records are editable by database operators and are **not tamper-proof or compliance-certified**. Review notes store the latest note; audit records preserve decision events, not every note revision.
- Editing a document invalidates dependent reports; historical source snapshots and re-analysis of an existing incident are future work.
- Synchronous analysis within one request, 64 KiB/1,200-line logs, no attachment archive, jobs, exports, retention automation, or load testing.
- Compose is a reproducible local demo, not a public deployment. Operational hardening, dependency/security review, backups, retention, concurrency limits, and a managed identity design are needed before real use.

Next improvements should start with a larger independently labeled evaluation, context/negation handling, immutable document revisions, and measured retrieval improvements. Semantic search is worth adding only if it improves that evaluation enough to justify its complexity.

## Project guide

- [API usage](docs/API.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Engineering decisions](docs/DECISIONS.md)
- [Retrieval and model integration](docs/MODELS.md)
- [Evaluation methodology and failures](docs/EVALUATION.md)
- [Verification record](docs/VERIFICATION.md)
- [Five interview questions](docs/INTERVIEW.md)

Original code is [MIT licensed](LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.md). No customer adoption, regulatory certification, hiring outcome, or business savings are claimed.
