# Prototype threat model

## Scope and assets

One fictional organization, synthetic logs, a small section-based runbook corpus, and local demonstration accounts. Protected assets are session credentials, incident ownership, restricted runbook text, reports derived from that text, review integrity, and the limited audit trail. Attackers may be anonymous clients, ordinary engineers guessing IDs, or text embedded in logs/runbooks. A compromised administrator, host, database, or provider is outside the protection boundary.

## Trust boundaries and controls

| Boundary / threat | Implemented control | Remaining limit |
| --- | --- | --- |
| Browser → login | Argon2 hashes, generic login error, persisted five-failure/ten-minute account throttle, origin check | No MFA, SSO, recovery, IP/global throttle, or account provisioning UI; account lockout abuse and concurrent throttling races remain |
| Browser → authenticated mutations | Opaque cookie session, HttpOnly, SameSite=Lax, session-bound CSRF header; origin checked when supplied | Local HTTP intentionally uses non-secure cookies; production requires HTTPS configuration but is not hosted or audited |
| Session storage | Only SHA-256 token digests, eight-hour expiry, active-user check, rotation on login, deletion on logout | No idle timeout, session-list UI, device binding, or advanced anomaly detection |
| Engineer → incident/source IDs | Ownership and document ACL predicates in backend SQL; 404 for absent and inaccessible resources | Administrators intentionally have broad access; clearance is a boolean, not a grant system |
| Retrieval → external model | ACL applied before materializing rows; redacted evidence and only permitted document sections are serialized | Access is evaluated at query time; no cross-request locking of clearance changes |
| Saved report → reader | Recheck all retrieved source IDs/versions against current access; withhold whole report on mismatch | Previously viewed/downloaded content cannot be revoked; logs and owner-authored titles are retained |
| Untrusted logs/files → parsers | Actual ASGI body limit 80 KiB, log limit 64 KiB/1,200 lines, strict UTF-8/control validation, no filename/path use | No edge rate limit, job queue, streaming parser, retention quotas, or load testing |
| Text → browser | Dynamic values escaped; source Markdown rendered as plain text; restrictive CSP, frame and content-type headers | No full independent accessibility or penetration audit |
| Text → provider | Data/instruction separation, no model tools, strict output shapes, fixed category and allowed-reference checks | Prompt injection and unsupported prose remain possible; mock tests do not establish live model safety |
| Secrets → storage/provider | Redaction of common labeled secrets, bearer/basic headers, userinfo URLs, JWT shapes, selected key prefixes and PEM private-key blocks; stable line positions | Encodings, unlabelled secrets, whitespace/quoted complex values, alternate key formats and personal data may escape detection |
| Review → persistence | Incident row lock and decision/note/audit write in one transaction; permission check and current-source gate | A permitted reviewer can change their decision; only latest note is stored |
| App → audit | Explicit actor, timestamp, action, constrained metadata | DB operators can edit/delete records; not tamper-proof, signed, or compliance-certified |

The model has no network tools, shell tools, or authorization APIs. It cannot grant itself access, and the application does not execute suggested diagnostic checks. Text recommendations may still be wrong or unsafe to follow; human inspection remains required.

## Data handling

Logs, titles, document input, and review notes are redacted before persistence. Provider input is redacted again. Application logs record event IDs and analysis modes, not input bodies, tokens, passwords, or provider response text. Uvicorn access logging is disabled in the supplied application command. Database URLs and provider keys belong in environment settings, never source files or chat.

The raw upload filename is ignored and uploaded content is never written as an executable file. There is no automatic log forwarding. External traffic occurs only when a maintainer explicitly enables the provider and supplies its key; provider retention/residency policies are not controlled by this prototype.

## Tests and nonclaims

Tests cover direct restricted document IDs, another engineer's incident/review/audit IDs, admin endpoints, CSRF, session expiry/logout/user deactivation, clearance revocation, source version/archive changes, input limits, common-secret patterns, and provider context isolation. Adversarial text checks show the deterministic path cannot change its fixed checks; mocked adapter checks verify request construction and validation. They do not prove resistance to live adversarial models or compromised administrators.

Use synthetic inputs. Before real deployment, independently review identity/authorization, dependency vulnerabilities, operational throttles and resource budgets, HTTPS/proxy headers, backup/restore, retention and deletion, secret handling, concurrency, and incident response. No guaranteed security, production readiness, regulatory certification, or factual correctness is claimed.
