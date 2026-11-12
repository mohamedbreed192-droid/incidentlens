# Verification record

Local verification was performed on November 12, 2026. This file records performed checks, not promised future checks. Machine-readable evidence is in [verification.json](verification.json); evaluation details and failures are in [results.json](../evaluation/results.json).

| Check | Observed result |
| --- | --- |
| Python tests against real PostgreSQL | 49 passed; zero failures/errors; 94% statement coverage |
| SQL schema | Alembic upgrade from empty DB, metadata comparison, GIN index inspection, committed-row visibility from another connection |
| Backend access controls | Restricted retrieval/direct IDs, other engineers' incidents/reviews/audits, admin writes/audit, CSRF, revoked clearance, changed/archived sources all exercised |
| Static checks | Ruff lint/format and JavaScript syntax checks passed |
| Docker image and startup | Non-root app built and started after the one-shot migration; ready health check passed |
| Separate fresh database | Migration applied before app start; no accounts until explicit seed; interactive seed CLI; zero starting incident count; correct permitted library; login/logout passed |
| Desktop browser | 1440×1000: login, submission, evidence, source dialog, keyboard dismissal, accept/review audit, history, authorized library, admin API denial, unknown-file upload, abstention, logout passed |
| Mobile browser | 390×844: same workflow and no horizontal document overflow passed |
| Administrator browser | Create section, edit/archive, version increment, inspect administrative audit, and logout passed |
| JavaScript browser errors | None recorded in the checked workflows |
| Evaluation | 40 cases; all individual predictions and four retained classification failures published |
| External provider | Real adapter exercised through HTTP mocks and pipeline mocks; no live paid calls performed |

The local pytest run reports two non-failing upstream notices: a Starlette/AnyIO deprecation and Alembic's inability to alter a computed column default. The schema comparison still finds no upgrade operations. Neither warning was hidden to obtain a passing result.

The managed environment required its CA bundle as an optional Docker build secret for package installation. The certificate was mounted for that step and was not copied into image layers. A second local Compose stack initially hit a port conflict and the environment's disk limit; disposable task containers/caches were cleaned, and the fresh-database application checks then completed on port 18080. These are development-environment observations, not app performance measurements.

The first browser run was followed by a clean screenshot capture with no transient success toast obscuring the report. Screenshots are actual application output with synthetic data. They are not rendered design mockups.

GitHub Actions repeats PostgreSQL tests, evaluation, and the desktop/mobile/administrator browser workflows and uploads its raw evidence. Inspect [the actual workflow runs](https://github.com/mohamedbreed192-droid/incidentlens/actions/workflows/ci.yml) for commit-specific remote status; the badge and run logs are authoritative.

## Not verified

Live OpenAI/Granite/watsonx behavior, paid model quality or cost, semantic search benefits, public backend hosting, production security, independent accessibility certification, load/concurrency capacity, disaster recovery, regulatory compliance, and real-customer impact were not tested or claimed.
