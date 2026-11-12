# API usage

Open `/api/docs` on the running local application for its generated OpenAPI reference. The supplied Swagger page uses CDN assets and is outside the application's restrictive page CSP; the core UI uses only local assets. Example values below are synthetic placeholders, never service credentials.

## Authenticate and retain CSRF state

`POST /api/auth/login` accepts:

```json
{"username":"engineer","password":"YOUR_LOCALLY_CHOSEN_DEMO_PASSWORD"}
```

A successful response sets `incidentlens_session` and returns `user` and `csrf_token`. Keep the cookie in your HTTP client's cookie jar. Send the returned token as `X-CSRF-Token` on every authenticated POST/PUT. Browser origins must match `ALLOWED_ORIGIN` when an Origin header is supplied. `GET /api/auth/me` returns the current user and CSRF token; `POST /api/auth/logout` revokes the session.

For a small Python client that prompts rather than puts a password in shell history:

```python
import getpass
import httpx

with httpx.Client(base_url="http://localhost:8000") as client:
    login = client.post("/api/auth/login", json={
        "username": "engineer", "password": getpass.getpass("Local demo password: ")
    })
    login.raise_for_status()
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    response = client.post("/api/incidents", json={
        "title": "Synthetic database failure",
        "log_text": "INFO start\nERROR postgres connection refused at db:5432"
    })
    response.raise_for_status()
    incident_id = response.json()["id"]
    report = client.get(f"/api/incidents/{incident_id}")
    report.raise_for_status()
    print(report.json()["report"])
    client.post(f"/api/incidents/{incident_id}/review", json={
        "decision": "accepted", "note": "Synthetic listener check completed by a human."
    }).raise_for_status()
    client.post("/api/auth/logout").raise_for_status()
```

This creates persistent synthetic records; it does not run the suggested checks.

## Endpoints

| Method / path | Behavior / authorization |
| --- | --- |
| `GET /api/dashboard` | Counts visible incidents by review state |
| `GET /api/incidents?offset=0&limit=40` | Visible history, newest first; limit 1–100, nonnegative offset |
| `POST /api/incidents` | JSON `title` and `log_text`; creates incident and report, returns 201 + `id` |
| `POST /api/incidents/upload` | Multipart `title`, `file`; contents validated, filename ignored |
| `GET /api/incidents/{id}` | Own incident, or any incident for an administrator; report source gate rechecked |
| `POST /api/incidents/{id}/review` | `decision`: `accepted`/`rejected`, optional `note`; requires supported current report |
| `GET /api/incidents/{id}/audit` | Same incident authorization; actor/action/time/decision metadata |
| `GET /api/documents` | Active permitted sections; administrator list also includes archives |
| `GET /api/documents/{id}` | Active permitted section; inaccessible/archived/absent → 404 |
| `POST /api/documents` | Administrator only; creates section at version 1 |
| `PUT /api/documents/{id}` | Administrator only; full replacement input, increments version; `active=false` archives |
| `GET /api/admin/audit` | Administrator only; latest 100 action records |
| `GET /health/live` | Process liveness; unauthenticated |
| `GET /health/ready` | DB access/migration table readiness; unauthenticated |

Document input:

```json
{
  "key":"TEAM-001",
  "title":"Synthetic escalation guidance",
  "section":"Read-only diagnosis",
  "access":"shared",
  "content":"Inspect approved monitoring and record observations for the service owner.",
  "active":true
}
```

Keys must use 3–40 uppercase letters, digits, or hyphens. Title/section/content limits are in OpenAPI. No delete-document endpoint is provided; archive preserves references. There is no user-provisioning or permission-changing HTTP endpoint.

## Report shape and limits

A report includes `status`, `category`, `mode`, `provider`, `model`, `observed`, `explanations`, `checks`, `citations`, and, for fresh analysis, `latency_ms`. Each observation contains an actual `line` and redacted `text`. Explanations contain text, observed line references and source IDs; checks contain text and source IDs. The server supplies citation title/section/version from retrieved documents. `fallback_reason` is a fixed safe code when a provider attempt fails.

`status=insufficient_evidence` has no explanation, checks, or citations. It can mean unknown/conflicting evidence, no supported accessible core runbook, or a withheld report after source changes. A withheld report has `mode=withheld` and exposes no original model/context detail.

Log bounds are 64 KiB of UTF-8 bytes and 1,200 lines. Empty text, invalid UTF-8, and unsupported controls fail validation. The whole actual request body, including JSON encoding/multipart overhead, is bounded to 80 KiB. Secret redaction is incomplete by design; clients should use synthetic inputs.

## Error handling

`401`: sign-in required or bad login; `403`: role, CSRF, or origin denied; `404`: absent/inaccessible ID; `409`: duplicate document key or unsupported review; `413`: oversized request envelope; `422`: invalid fields/log; `429`: login throttle; `503`: database readiness failed. Provider failures fall back to a labeled baseline report rather than returning provider exception text. The browser presents validation/error messages and loading states.
