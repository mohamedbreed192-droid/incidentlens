# Five questions to explain your project

1. **Why a modular monolith with PostgreSQL full-text search?** Explain the single-organization scope, module boundaries, generated search vector/GIN index, category queries and lexical limits. Describe what evidence would justify semantic retrieval or a job queue.

2. **Where is authorization enforced, and what happens after access changes?** Trace incident ownership and document predicates through direct endpoints, retrieval, provider context, citations and audit access. Explain why the report tracks every retrieved document version and why a valid-looking UUID is not permission.

3. **What does the baseline actually do, and what does the model adapter add?** Walk through one log's redaction, observed line extraction, single-category gate, retrieval, supported template, optional real HTTP call, structured-output/reference validation, and labeled fallback. Be explicit that no live-model evaluation was performed.

4. **What do the evaluation numbers demonstrate, and where did it fail?** Define the valid-log accuracy denominator, oracle-category Recall@3 versus end-to-end retrieval, author-rubric support and citation validity. Explain all four retained failures, especially why UN10 has valid citations but an unsupported conclusion.

5. **How are sessions, reviews, and persistence protected and tested?** Explain Argon2 versus token hashing, opaque cookie sessions, CSRF, expiry/logout, review row locking and same-transaction audit writes. Show PostgreSQL migrations, a second-connection persistence test, browser evidence, and the limits of editable audit records and local Compose hosting.
