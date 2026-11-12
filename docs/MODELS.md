# Retrieval and model integration

## Deterministic path

1. Validate UTF-8 bytes, text controls, byte count and line count; normalize CRLF/CR newlines.
2. Redact common secret patterns while preserving line counts. All later stages and storage use this redacted representation.
3. Match explicit regular expressions per log line. One matching category selects evidence lines; zero or multiple categories abstain. At most eight matched lines enter a report/provider request.
4. Map the category to a documented query in `retrieval.py`. PostgreSQL filters active/shared/cleared documents in the query, matches the generated English search vector, and ranks up to three sections.
5. Require the category's core runbook and its reviewed diagnostic-check text. The baseline does not synthesize arbitrary runbooks into new advice.
6. Build a tentative explanation and cited checks. Persist the report with all retrieved source IDs/versions. Recheck them on later report reads.

No model runs in baseline mode. Search ranking and regular expressions are not presented as live AI. Fixed lexical rules miss paraphrases and negation; the evaluation preserves examples of both.

## Implemented external adapter

`ModelProvider` defines `async investigate(payload) -> ProviderReport`. `OpenAIProvider` is a real configurable HTTPS integration using httpx and `https://api.openai.com/v1/chat/completions`. The provider origin is fixed, preventing a document or browser request from choosing a credential destination. Configurable fields are API key, model name, and timeout; no SDK, tool calls, agent framework, or automatic retries are used.

The request has a system instruction treating all logs and documents as untrusted data, followed by a JSON data message containing the proposed category, observed line-number/text pairs, and permitted runbook sections. Content is redacted again before sending. The request includes a JSON schema generated from Pydantic models, strict output mode, and a maximum completion token count.

The returned JSON must have only the allowed fields, bounded explanation/check lists and text sizes, the same category, observed log line references, and allowed source IDs. Source titles, section names, and versions are resolved by the server, not trusted from generated output. The application records the actual successful provider/model or a baseline mode with a safe fallback reason. It does not display provider exception bodies.

Timeouts, network errors, HTTP 429/other errors, oversized or malformed responses, missing credentials, and invalid references fall back to the already useful deterministic report. Unknown/ambiguous or unsupported-source incidents abstain without a provider call. There are no retries that could unexpectedly multiply usage.

## What was actually verified

httpx mock transports exercised the real adapter's URL, headers, request/schema construction, redaction, successful decoding, timeout, HTTP 401/429/503, malformed JSON, empty responses, and missing configuration. Pipeline mocks tested successful model provenance, baseline fallback, allowed source context, and hallucinated ID rejection. No paid credentials were configured, no live external call was made, and no live model quality or injection-resistance claim is made.

A valid schema and existing citation ID establish structure and access, not entailment. The provider can still generate unsupported prose or follow hostile text. No live-model scores are included in the baseline evaluation.

## Practical IBM watsonx / Granite extension path

This is a documented path, **not an implemented adapter**:

1. Implement another `ModelProvider` in `providers.py` or a small sibling module. Keep the existing authorization, redaction, support gate, and reference validation unchanged.
2. For IBM watsonx.ai, use the official current SDK/REST documentation for IAM authentication, regional endpoint, project/space ID, and an available Granite model. Configure credentials in environment settings, cache access tokens only with their expiry, set timeout/output limits, and map responses into `ProviderReport`.
3. A local Granite model served through a maintained inference runtime is another option. Treat an OpenAI-compatible transport as a new explicitly trusted provider configuration; do not let uploaded text or public requests set an arbitrary URL or reuse the OpenAI credential.
4. Verify the selected model's structured-output support. If it lacks strict JSON-schema output, still parse and reject invalid JSON with Pydantic and the existing reference checks. Never repair invented source IDs silently.
5. Add transport and failure mocks, then use an explicitly budget-approved live smoke test. Record exact model version, provider, prompt version, costs if measured, and failures. Repeat an independently labeled evaluation before claiming a benefit over the baseline.

Watsonx offerings, Granite model availability, endpoint schemas, and licensing may change. Follow the official [watsonx.ai documentation](https://www.ibm.com/docs/en/watsonx) and [Granite repository](https://github.com/ibm-granite). The project has no IBM affiliation or endorsement.
