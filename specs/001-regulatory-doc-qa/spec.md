# Feature Specification: Regulatory Document QA (Production RAG)

**Feature Branch**: `001-regulatory-doc-qa`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: "A self-hosted document question-answering system for acronym-dense regulatory and fiscal PDF corpora, aimed at teams that cannot send sensitive documents to external services. Grounded answers with verifiable citations, a published evaluation table across chunking/retrieval configurations and two vector backends, single-VPS operation with cost/latency/eval dashboards, budget caps, local-model fallback, a security gate, and consumption via HTTP API and MCP tools. Practitioner research: docs/research/reddit-rag-scan-2026-07.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a question, get a cited answer (Priority: P1)

A compliance analyst has a corpus of regulatory/fiscal PDFs already ingested. They ask a natural-language question ("What is the weight tolerance for cargo classified under code X?") and receive an answer grounded in the corpus, with citations naming the source document, page, and the exact supporting excerpt. When the corpus does not contain the answer, the system says so explicitly instead of guessing.

**Why this priority**: This is the product. Everything else (ingestion, evals, dashboards) exists to make this answer trustworthy. It is also the demo a hiring manager or client sees first.

**Independent Test**: With a pre-ingested fixture corpus, submit 10 questions with known answers and 3 questions the corpus cannot answer. Verify each answered question carries at least one citation resolving to a real document+page containing the supporting text, and all 3 unanswerable questions return an explicit "not found in the corpus" response.

**Acceptance Scenarios**:

1. **Given** an ingested corpus containing the answer, **When** the user asks the question, **Then** the response contains the answer, at least one citation (document, page, excerpt), and the excerpt actually supports the answer.
2. **Given** a question whose answer is not in the corpus, **When** the user asks it, **Then** the system responds "not found in the corpus" (or equivalent) and does not fabricate an answer.
3. **Given** a question containing a domain acronym or exact code (e.g., a fiscal document ID), **When** the user asks it, **Then** retrieval finds the passages containing that exact identifier.
4. **Given** any answered question, **When** the response is returned, **Then** it includes the cost incurred to produce it.

---

### User Story 2 - Ingest messy real-world PDFs (Priority: P2)

An operator uploads a batch of real regulatory PDFs — including scanned pages, tables, and mixed layouts. The system ingests them, reports per-document status (pages processed, text extracted vs. OCR-required, failures), and makes them queryable. Re-uploading the same document does not create duplicates.

**Why this priority**: Without trustworthy ingestion there is nothing to retrieve; messy-PDF parsing is the #3 practitioner pain (64/139 posts). Ranked below P1 because a fixture corpus can demo P1 while ingestion hardens.

**Independent Test**: Upload a fixture set of 20 PDFs (clean digital, scanned, table-heavy, corrupted). Verify status report accuracy, that the corrupted file fails gracefully with a clear message, and that the other 19 become queryable.

**Acceptance Scenarios**:

1. **Given** a batch containing digital and scanned PDFs, **When** ingestion completes, **Then** each document shows a status (succeeded/failed, pages, extraction method) and succeeded documents are queryable.
2. **Given** a document already in the corpus, **When** it is uploaded again, **Then** the system deduplicates and reports it as already present.
3. **Given** a corrupted or password-protected file, **When** ingestion runs, **Then** the file is rejected with an actionable error and the rest of the batch is unaffected.

---

### User Story 3 - Published evaluation table (Priority: P3)

A maintainer runs the evaluation suite against a golden dataset (≥50 question/answer/source triples). The suite produces a table scoring every configuration — chunking strategy (fixed, recursive, semantic) × retrieval mode (vector, keyword, hybrid; each ± reranking) × vector backend (primary, benchmark) — on retrieval recall@k, answer faithfulness, answer relevance, and citation accuracy. Results persist over time; a release is blocked when scores regress against the baseline.

**Why this priority**: Measurement is the credibility engine of the project (constitution Principle I) and the #1 differentiator vs. tutorial builds — but it needs P1's pipeline to exist before there is anything to measure.

**Independent Test**: Run the eval suite twice: once on the baseline configuration, once after an intentionally degraded configuration (e.g., absurd chunk size). Verify the table reports both runs, the degradation is visible in the scores, and the regression check flags it.

**Acceptance Scenarios**:

1. **Given** the golden dataset and a configured pipeline, **When** the eval suite runs, **Then** a results table is produced covering all configured combinations with the four metrics.
2. **Given** a configuration change that lowers a metric beyond the tolerance, **When** the regression check runs, **Then** the change is flagged as blocking.
3. **Given** two eval runs at different times, **When** the maintainer views results, **Then** both runs are comparable side by side (trend over time).

---

### User Story 4 - Operate it from one machine (Priority: P4)

An operator brings the entire system up on a single VPS with one command, and watches dashboards for latency, token usage, cost per query, and eval-score trends. Alerts fire on cost drift and eval regressions. Per-query and daily budget caps reject over-budget requests before any paid call is made. When the external LLM provider is unavailable (or forbidden by policy), the system degrades to a local model and keeps answering.

**Why this priority**: Operability is what makes it "production" rather than a demo — but it wraps the pipeline built in P1–P3.

**Independent Test**: From a clean machine: one command brings all services up; dashboards populate after 10 test queries; setting a $0 daily budget causes the next request to be rejected with a budget error and zero external spend; disabling the external provider causes answers to come from the local fallback, marked as degraded.

**Acceptance Scenarios**:

1. **Given** a clean host, **When** the operator runs the single startup command, **Then** all services start and the system answers a test query.
2. **Given** a configured daily budget already consumed, **When** a new question arrives, **Then** it is rejected before any external call with a clear budget message.
3. **Given** the external LLM provider is unreachable, **When** a question arrives, **Then** the system answers via the local fallback and labels the response as degraded.
4. **Given** an eval regression or cost drift beyond threshold, **When** it occurs, **Then** an alert is raised.

---

### User Story 5 - Consume it as a tool from an LLM client (Priority: P5)

A developer connects an LLM client (agent) to the system and uses document QA and raw retrieval as callable tools, with the same security, budget, and citation guarantees as the HTTP interface.

**Why this priority**: Second consumption surface; high market-signal value (MCP), but the guarantees must exist first.

**Independent Test**: From a standard MCP-capable client, list tools, call retrieval and QA against the fixture corpus, and verify parity of results and guardrails with the HTTP API.

**Acceptance Scenarios**:

1. **Given** a connected LLM client, **When** it lists available tools, **Then** document QA and retrieval tools appear with usable descriptions and schemas.
2. **Given** a tool call with an over-budget request, **When** it executes, **Then** it is rejected with the same budget semantics as the HTTP API.

---

### Edge Cases

- Question in Portuguese against an English document (or vice versa) — retrieval must not silently return nothing; behavior: answer from cross-language retrieval when possible, otherwise explicit "not found."
- A query that is itself a prompt-injection attempt ("ignore your instructions and…") — the security gate screens it; the pipeline never executes instructions from documents or queries.
- A document whose content contradicts another document — answer surfaces both sources and notes the conflict rather than silently choosing one.
- Uploaded PDF containing personal data (CPF/CNPJ, names) — PII in *queries* is masked before external calls; document PII stays inside the self-hosted boundary by design.
- Corpus grows past single-node comfort (e.g., 10× target volume) — ingestion and query still function; performance targets may degrade gracefully with documented limits.
- The golden dataset itself contains an error — eval runs support annotating/excluding disputed cases with an audit note, rather than editing history silently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST answer natural-language questions about ingested documents, grounding every answer in retrieved passages.
- **FR-002**: Every answer MUST include citations: source document, page, and supporting excerpt; citations MUST resolve to real corpus content containing the cited text.
- **FR-003**: When no sufficient grounding exists, the system MUST return an explicit "not found in the corpus" response and MUST NOT fabricate.
- **FR-004**: System MUST retrieve passages containing exact identifiers, codes, and acronyms even when they have no semantic meaning (keyword-capable retrieval).
- **FR-005**: System MUST ingest PDF documents including scanned pages, tables, and mixed layouts, reporting per-document ingestion status and failures without aborting the batch.
- **FR-006**: System MUST deduplicate re-uploaded documents.
- **FR-007**: System MUST maintain a golden dataset (≥50 question/answer/source triples) and an evaluation suite scoring retrieval recall@k, answer faithfulness, answer relevance, and citation accuracy.
- **FR-008**: The evaluation suite MUST compare all configured combinations of chunking strategy (fixed, recursive, semantic), retrieval mode (vector, keyword, hybrid, each with and without reranking), and both vector backends, producing a persisted, publishable results table.
- **FR-009**: A release MUST be blocked when evaluation scores regress beyond a configured tolerance against the baseline.
- **FR-010**: Every answer MUST report the cost incurred to produce it (token usage and monetary estimate).
- **FR-011**: System MUST enforce per-query and per-day budget caps, rejecting over-budget requests before any external paid call.
- **FR-012**: System MUST cache repeated identical requests to avoid redundant paid calls.
- **FR-013**: System MUST fall back to a locally hosted model when the external provider is unavailable or disabled by policy, labeling such answers as degraded.
- **FR-014**: A security gate MUST rate-limit clients, screen inputs for prompt-injection patterns, detect and mask PII in queries before any external call, and validate outputs before returning them.
- **FR-015**: All document content and derived data MUST remain within the self-hosted boundary; only masked query context may reach external LLM providers.
- **FR-016**: Operators MUST be able to start the entire system on a single host with one command, and observe dashboards for latency, token usage, cost per query, and eval trends, with alerts on cost drift and eval regression.
- **FR-017**: System MUST be consumable via an HTTP API and via MCP tools (document QA and retrieval), with identical guarantees (citations, budgets, security) on both surfaces.
- **FR-018**: Every pipeline stage (ingest, chunk, embed, retrieve, rerank, generate) MUST be individually traceable with timing, token, and cost attribution per request.

### Key Entities

- **Document**: An ingested source file; attributes: identity/fingerprint (for dedup), title, language, page count, ingestion status, extraction method per page.
- **Chunk**: A retrievable passage derived from a document; attributes: parent document, page span, text, chunking strategy that produced it, metadata (section, detected identifiers).
- **Query**: A user question; attributes: text, masked-PII form, requester, timestamp, budget context.
- **Answer**: The system's response; attributes: text or "not found," citations, cost report, degraded flag, configuration used.
- **Citation**: Link from an answer to a chunk; attributes: document, page, excerpt, support score.
- **Golden Case**: A question/expected-answer/expected-source triple used by the eval suite; attributes: status (active/disputed/excluded), audit notes.
- **Eval Run**: One execution of the suite; attributes: timestamp, configuration matrix, metric scores, baseline comparison verdict.
- **Budget Ledger**: Record of per-query and daily spend; attributes: period, caps, consumed, rejected-request count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the golden dataset, at least 90% of answerable questions receive answers whose citations resolve to genuinely supporting passages (citation accuracy ≥ 0.9 on the best configuration).
- **SC-002**: 100% of unanswerable golden-dataset questions return an explicit "not found" response — zero fabricated answers in eval runs.
- **SC-003**: Queries containing exact codes/acronyms achieve at least 25% higher retrieval recall on the best hybrid configuration than on pure semantic retrieval, demonstrated in the published table (validating the hybrid-by-default design).
- **SC-004**: A new operator can go from clean host to first cited answer in under 30 minutes using only the README.
- **SC-005**: 95% of questions return answers in under 10 seconds at the target corpus scale (10,000 documents / ~500,000 chunks) on a single commodity VPS.
- **SC-006**: Median cost per answered question stays under US$0.02 at default configuration, and the system can prove it from its own ledger.
- **SC-007**: Zero secrets, PII, or third-party corpus content present in the public repository across its entire history.
- **SC-008**: An intentionally introduced retrieval degradation is caught by the regression gate before release in 100% of test cases.

## Assumptions

- **Corpus language**: primary corpus is Portuguese (BR) regulatory/fiscal documents, with English documents supported; the golden dataset includes both languages. (Chosen because the owner controls such a corpus and it is maximally acronym-dense; the pipeline itself is language-agnostic.)
- **Tenancy**: single-tenant, single-team deployment per instance; user-level authentication is a simple shared-key/API-token model in v1 — full identity management is out of scope.
- **Scale target**: up to ~10,000 documents / ~500,000 chunks per instance in v1; beyond that is out of scope but must degrade gracefully.
- **Corpus sensitivity**: documents are sensitive but not classified; the self-hosted boundary plus query-PII masking is sufficient — full air-gap operation is supported via the local-model fallback but not the default mode.
- **Golden dataset authorship**: curated manually by the maintainer from the corpus; LLM-assisted drafting is allowed but every case is human-verified before entering the active set.
- **The published eval table** is a repository artifact (regenerated by the suite), not a hosted web page, in v1.
- **Reranking tolerance**: "regression beyond tolerance" defaults to any metric dropping more than 2 points (on a 0–100 scale) vs. baseline; tunable per metric.
