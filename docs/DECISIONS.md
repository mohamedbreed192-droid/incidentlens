# Engineering decisions

## One deployable application and one PostgreSQL database

The problem is a short, human-reviewed investigation, not a distributed event-processing system. A modular monolith keeps authentication, incident persistence, retrieval, and review transactions explainable to a student maintainer. FastAPI handles HTTP; SQLAlchemy maps tables and constructs parameterized queries; Alembic records schema changes that can be applied to an empty database. JSONB stores a report snapshot while relational columns hold ownership and review state.

The interface uses browser JavaScript and hash routes. It calls the same authenticated backend for every action; route visibility has no authority. There is no frontend dependency/build chain. This limits type sharing and client-side structure but makes the small interface easy to run and inspect.

## Full-text search before embeddings

Each runbook section has an English `tsvector` generated from title, section, and content, indexed with GIN. The parser maps a recognized category to a small explicit search query. SQL applies active/access predicates before selecting at most three ranked rows. Rank ties use the stable runbook key.

This is a lexical baseline, not semantic search. Retrieval with a supplied labeled category finds the appropriate core runbook in all 24 known-category evaluation cases; end-to-end retrieval misses three because classification abstains. Adding an embedding service would not fix those classification gaps by itself. The small corpus and broad category queries limit what the retrieval measurement demonstrates.

## Useful baseline before external generation

Known signals select a tentative category template and two read-only diagnostic checks. The associated core runbook must be retrieved and contain the check text. If it is missing, restricted, archived, edited beyond support, or displaced from the top three, the report abstains. Multiple recognized categories also abstain rather than imposing an arbitrary priority.

The external adapter can rephrase or expand within a validated structure only after the baseline evidence/support gate succeeds. Unknown logs never go to the provider. Returned line numbers must be observed evidence lines; source IDs must be from the already authorized retrieval set. This cannot establish entailment of generated prose, so the UI keeps interpretation tentative and human review explicit.

## Opaque sessions and backend authorization

Passwords use pwdlib's Argon2 implementation. Login creates a random session ID and stores only its SHA-256 digest in PostgreSQL, with an eight-hour absolute expiry. The raw token is an HttpOnly, SameSite=Lax cookie. There is no JWT in browser storage. Login rotates the browser's previous session; logout deletes it. A session-bound HMAC supplies the CSRF header. Production configuration requires secure cookies and an HTTPS browser origin.

An engineer's incident query always includes ownership. Source queries always include current access/active predicates. Administrators are an explicit role. The seed command defines demo roles and clearance, but there is no user-management interface. Account-level login throttling is durable; it is intentionally simple and can also let an attacker temporarily lock out a known username. A production identity provider would address lifecycle and stronger abuse controls.

## Invalidate rather than reconstruct historical sources

Reports store all retrieved document IDs and versions. Every report read checks them against the reader's current accessible active set. Any mismatch withholds explanation, evidence snapshot, checks, and citations. This also protects uncited model context after clearance revocation.

This simple conservative rule can hide a baseline report because an unused retrieved document changed. It avoids keeping historical sensitive text and makes stale citations uninspectable by design. Immutable revisions and explicit per-source provenance would be a useful next iteration; source permission revocation would still need to apply to historical revisions.

## Review and audit consistency

A review locks the incident row and writes the decision, latest note, review timestamp, and audit event in one database transaction. A later review can replace the current state; the decision events remain in the application audit table. Notes are not copied into audit metadata. Database operators can edit these records, so this is not an immutable ledger or compliance artifact.

## Conservative local operation

Compose binds ports to loopback, runs the app as a non-root user, waits for PostgreSQL health, and applies migrations before app startup. The seed is explicit and forbidden in production mode. Local secrets are randomly generated into an ignored file; no demo password is silently selected by the application. Dependency lock files pin the resolved Python environment, but image tags are not digest-pinned and dependencies require ongoing maintenance. These choices support a reproducible student demo without claiming production readiness.
