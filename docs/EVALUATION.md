# Evaluation method and actual failures

## Dataset and separation

`evaluation/cases.json` is a fixed 40-case synthetic set: eight logs per supported category (24), twelve unknown/ambiguous logs, and four invalid inputs. `fixtures/development/` provides separate short walkthrough examples. All material was author-written; separation of files is not independent data collection or a blinded benchmark. Do not infer enterprise performance from these scores.

The seeded corpus has six runbook sections: three shared core troubleshooting sections, one restricted database section, one irrelevant onboarding section, and one adversarial instruction example. The evaluation runs as the uncleared `engineer` account. Restricted documents must not enter its retrieval result. Dedicated integration tests also exercise cleared/uncleared users, guessed IDs, and clearance revocation.

## Definitions

- **Classification accuracy:** exact proposed category agreement over the 36 valid logs. Invalid input is measured separately, not counted as correct incident classification.
- **Recall@3 with oracle category:** for each of 24 known-category cases, feed its labeled category to retrieval. The denominator is the number of relevant **accessible** source keys labeled in that case; here each has one. Compute `|relevant ∩ retrieved top 3| / |relevant|`, then average. Unknown/invalid cases have no relevant source and are excluded. This deliberately isolates search from parser errors.
- **End-to-end retrieval hit rate:** on those same 24 known cases, retrieve using the actual predicted category and count cases containing the labeled core source. Abstention is a miss. It is lower than oracle retrieval and shows the parser's practical effect.
- **Citation validity/accessibility:** verify emitted source ID exists in the reader's currently permitted active set and stored version/section match. Also verify observed log line numbers and text against the redacted supplied log. No score is manufactured for empty citations.
- **Evidence support:** the author reviewed the three fixed templates against their runbook sections using `assessments.json`. Explanations must remain tentative and within the section's alternatives; each diagnostic check must appear in that source. An emitted case counts supported only if this template rubric passes and the predicted category matches the case label. The quoted-example false positive has an explicit unsupported case override. This is a small author-assessed proxy, not independent factual entailment scoring, expert root-cause confirmation, or live-model quality evaluation.
- **Insufficient evidence:** separately count abstention on the twelve unknown/ambiguous cases and inappropriate abstention on twenty-four known cases.
- **Latency:** one warmed serial pass over 36 valid cases, measured by `perf_counter`. Includes parsing/redaction, actual retrieval, additional oracle retrieval measurement, and analysis (which performs its own retrieval). Excludes login/HTTP, browser, external provider, cold startup, concurrent load, and invalid cases. p95 is the nearest-rank 95th percentile; no production performance inference is warranted.

## Recorded local run

Full per-case results and exact runtime metadata are in [results.json](../evaluation/results.json). Python 3.12.14; PostgreSQL 16.15; Linux x86-64; deterministic baseline; warm local Docker database.

| Measure | Result |
| --- | --- |
| Exact valid-log category agreement | 32/36 = 88.9% |
| Oracle-category Recall@3 | 24/24 = 100% |
| End-to-end core-source hit | 21/24 = 87.5% |
| Valid, version-matched, accessible citations | 22/22 |
| Valid observed log references | All emitted references matched |
| Author-rubric evidence support | 21/22 emitted reports |
| Unknown/ambiguous abstention | 11/12 |
| Incorrect known-category abstention | 3/24 |
| Malformed inputs rejected | 4/4 |
| Analysis/evaluation median / p95 / maximum | 4.591 / 9.003 / 12.625 ms |
| Incident-creation HTTP median / p95 / maximum | 8.939 / 12.500 / 50.636 ms (36/36 HTTP 201) |

### Actual HTTP request timing

`benchmark_http.py` submits the 36 valid frozen cases to `POST /api/incidents` on the running single-worker Docker demo. It authenticates once and measures each complete POST response with `perf_counter` using HTTP/1.1 keep-alive, serial requests, a warm application/database, and no concurrent load. It includes body parsing, redaction, authorization, retrieval, report generation, incident/audit persistence and commit, and response transport. Login, subsequent report-verification reads, browser rendering, external models and cold startup are excluded. The maximum 50.636 ms observation is retained; no cause for that outlier was established.

[http-results.json](../evaluation/http-results.json) contains every sample and the exact conditions. This is a small loopback experiment, not a load or production-latency benchmark. Run `python -m scripts.benchmark_http` against the local baseline demo to repeat it; the script deliberately creates synthetic incident records.

### Failures retained in the dataset

| Case | Expected / actual | Explanation |
| --- | --- | --- |
| DB08 | database / unknown | “connection lost after handshake” has no supported lexical signature |
| AU08 | credentials / unknown | “JWT signature verification mismatch” lacks the supported validity/failure wording |
| SV08 | service / unknown | “empty endpoint set” is not recognized as unavailable service evidence |
| UN10 | unknown / database | The parser treats a quoted training example as a current failure; valid source and line references do not repair this unsupported inference |

The rules were not expanded after observing these cases. Improving them should be measured on a new independent set to avoid optimizing to this small evaluation.

## Authorization, injection, and provider checks

The recorded backend suite passes 49 focused tests with real PostgreSQL and 94% statement coverage. Its authorization tests cover restricted source IDs and retrieval filtering, another engineer's incident/detail/review/audit requests and dashboard counts, administrator-only writes/audit, source clearance revocation, source version/archive invalidation, and CSRF/session controls. Test count includes parameterized cases; coverage is a statement measure, not a proof of security.

Prompt-injection text appears in valid logs and the corpus. An additional test appends a malicious instruction to a matching core source and verifies the baseline's fixed diagnostic checks remain unchanged. Removing the source's supporting check text causes abstention. Provider request mocks verify untrusted-data instruction placement, common-secret redaction, and omission of restricted documents; other mocks reject invented source IDs and unsupported line references. These are structural tests, not a live model red-team assessment.

No model credentials were configured. No live provider request, paid infrastructure, model-quality evaluation, watsonx integration, or semantic retrieval experiment was performed.

## Reproduce

After starting and explicitly seeding the Compose demo, install `requirements-dev.lock` in a local virtual environment and run:

```bash
python -m scripts.evaluate_local
python -m pytest --cov=app
python -m scripts.browser_check
```

The first command forces baseline mode, reads the local configuration without printing secrets, and writes a new results JSON. Latency naturally varies between machines/runs. CI runs the same dataset and uploads its own results and browser artifacts; it does not overwrite the committed local report. Consult the workflow run rather than assuming the badge passed.
