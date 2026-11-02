# Phased Plan

Current work: **phase 5 in progress** (code done offline, waiting for the Neon connection); phase 4 still awaits the user's walkthrough. The user explicitly authorized completing the whole phase with investigation, code review and tests. A real OpenAI call and LangSmith server-side verification succeeded. Docker step 2.2 remains deferred and remote CI execution is not independently verified. Phases 6–11 have not started.

The original two-day MVP target is an estimate, not a deadline promise. We progress through observable results and accept phases together. If a phase is too large for one clear manual check, split it into smaller steps before implementation.

Statuses: `not started` → `in progress` → `awaiting manual acceptance` → `accepted`. A failed check keeps work in progress. `Deferred` records an explicit user decision to postpone work; it never means completed. Automated checks do not replace the user's confirmation.

## How we complete each step

The [README](../README.md) describes the entire product; the [specification](spec.md) holds technical requirements. Phases divide implementation without reducing the original scope.

Choose one small result within the phase. Explain the data flow and how to observe the output, implement it, run checks, and report. The user repeats a short exercise, discusses the result, and confirms the next step. If a concept or result remains unclear, stay with that step and explain it. The earlier explicitly authorized parallel batch was a bounded exception to sequential implementation, not to manual acceptance.

Every report needs changed files, actual command results, manual instructions with expected output, a brief explanation of the new concept, and remaining limitations. Use examples from the project; do not build a separate teaching framework.

## What we learn and try

| Phase | Concept | User practice |
|---|---|---|
| 1 | Goal, specification, and definition of done | Follow the entire README workflow and compare it with the original task |
| 2 | HTTP API, environment, container, tests, and CI | Launch `/health`, read its response, and run its test; container practice is deferred |
| 3 | Requirements, evidence, and gold labels | Find a requirement and conflict in a transcript before using a model |
| 4 | Structured output, Pydantic, grounding, LangChain's role; state and a node through `extract` input/output | Run extraction, check a quote, and observe rejection of an unsupported quote |
| 5 | RAG, chunk, embedding, and top-k | Query the specification, read retrieved chunks, and inspect the classification rationale |
| 6 | Graph transitions and a bounded critic loop | Trace a story to a requirement and inspect critic feedback and revision limits |
| 7 | LangGraph assembly, interrupt, checkpoint, and idempotency | Pause at review, restart the service, resume after Approve, and repeat approval |
| 8 | SSE and traces | Follow one run's events and open its LangSmith trace |
| 9 | UI/API interaction | Complete the browser workflow and trace a story edit to the result |
| 10 | Precision, recall, F1, baseline, and LLM judging | Examine one omission, false positive, and threshold failure on concrete cases |
| 11 | Local versus deployed application, budgets, and cache | Run the public workflow, measure duration, and verify dry-run |

Explain technical terms before first use. Check library APIs against official documentation during implementation. Before phase 7, individual node functions can be explored in isolation; verify the full pause/resume workflow on the assembled graph in phase 7.

## Docker checkpoint: step 2.2

**User decision, 2026-11-02:** leave Docker deferred and continue work that does not need a database. This checkpoint must survive new agent sessions.

- Firmware virtualization is enabled; the processor supports virtualization and SLAT.
- WSL 2 and Windows Virtual Machine Platform are installed.
- Windows reports no active hypervisor. The user confirmed `hypervisorlaunchtype Off` using an administrator terminal.
- Docker Desktop initially returned Engine HTTP 500 and then displayed “Virtualization support not detected.” Container startup cannot currently be verified.
- Compose configuration validation passed: `docker compose --env-file .env.example config --quiet`. Health dependencies, loopback ports, environment wiring, and a named database volume were inspected. This does not prove container behavior.
- Still unverified: image build, API/database container startup, pgvector SQL behavior, and database persistence after container recreation.
- **Do not enable the hypervisor, modify boot settings, reboot, or retry Docker unless the user asks.** On 2026-11-02 the user chose Neon as the phase 5 database; this does not close step 2.2.
- Resume only after the user requests it and Docker Engine is available. Run the saved README container checks, including SQL and persistence, before accepting step 2.2. Revisit this choice before database-dependent phase 5 or earlier work requiring a live database.

## Phase 1. Instructions and plan

**Status:** accepted by the user on 2026-11-02. The English translation is a later documentation update awaiting review.

- Deliverable: README, AGENTS.md, CLAUDE.md, specification, plan, and decision log.
- Checks: local links resolve, requirements are consistent, and unfinished application features are not presented as working.
- Manual acceptance: open README, follow the documents, and review MVP scope and phase order.
- Done when: the user confirms the documents, including any agreed revisions.

## Phase 2. Local scaffold

**Status:** in progress. Corresponds to original item 1.1. Docker remains deferred, so the whole phase is not complete.

1. **2.1 — minimal API:** accepted on 2026-11-02. The user ran the server, `/health` and `/docs` returned 200, and pytest reported 1 passed.
2. **2.2 — local infrastructure:** Dockerfile, Compose with pgvector, and `.env.example` are prepared. Runtime verification is deferred; see the Docker checkpoint above. Database settings reach the API environment, but the application does not execute SQL yet.
3. **2.3 — CI:** implemented, awaiting manual review and the first remote Actions run. `.github/workflows/api.yml` installs locked dependencies and runs pytest, Ruff, and formatting on pushes and pull requests. Local checks pass; remote execution is not yet verified. The user explicitly authorized this step without waiting for deferred step 2.2.

- Deliverable: `apps/api`, FastAPI `/health`, Dockerfile, Compose with pgvector, `.env.example`, `.gitignore`, and CI for Ruff/pytest. No AI logic or UI.
- Checks: Ruff, health test, Compose configuration, and API/database startup when Docker is available. CI uses the same Python checks.
- Manual acceptance: launch the service using README, inspect `/health`, and inspect a real GitHub Actions run once changes are pushed. Container acceptance remains separate and deferred.
- Done when: the scaffold runs using documented commands, required checks pass, and manual acceptance is confirmed. A deferred check cannot be marked passed.

## Phase 3. Demo data and gold labels

**Status:** accepted by the user after reviewing and committing the corpus. Original items 1.2–1.3.

- Deliverable: one fictional client specification of roughly five pages, six realistic transcripts with small talk, changes of mind, and 3–4 planted specification conflicts. Six transcript-based gold cases plus six short synthetic cases.
- Project: `harbor-desk`; specification and transcripts under `data/demo/harbor-desk/`, gold JSON under `evals/cases/`.
- Fixture convention: root-relative `spec_path`; either `transcript_path` or inline `transcript`; requirements with quotes, speakers, labels, and stable `HD-*` specification heading references; `expected_stories` linked to requirements; open `questions`. Expected stories are gold expectations, not runtime Jira payloads. Runtime chunk IDs and idempotency keys come later.
- Annotation convention: expected stories cover new requirements; duplicate, conflicting, and unclear requirements do not create expected implementation stories in these fixtures. Policy changes stay in open questions. This is gold annotation, not implemented runtime behavior.
- Checks: all 12+ cases load; source references resolve; gold quotes appear in transcripts; expected conflicts are supported by the specification; requirement/story references are valid. These are fixture-integrity checks, not measured model quality.
- Manual acceptance: compare one transcript, its requirements, quotes, and conflict against the specification. The planned conflict topics are export permissions, audit retention, public sharing, and the booking window.
- Done when: the user accepts the fictional project and labels as the reference for future implementation. No LLM eval baseline is claimed at this stage.

Local verification for the current batch: pytest reports **6 passed** (one health test, one corpus check over 12 cases, and four corruption checks); Ruff lint and formatting pass. The corpus has one 2,011-word specification, six transcript files, six transcript-backed cases, and six inline synthetic cases. No Docker, LLM, or remote GitHub Actions run was used to claim these results.

## Phase 4. Contracts and requirement extraction

**Status:** implemented and verified, awaiting manual acceptance. Original item 1.5 and the shared LLM helper. RAG, stories, Jira and the HTTP extraction route are not included.

Small steps:

1. **4.1 — Requirement contract:** accepted. The user confirmed valid input is accepted and `priority="urgent"` produces ValidationError.
2. **4.2 — Grounding:** implemented in `app/grounding.py`, awaiting manual review. Filter structurally valid requirements by nonempty quote membership with whitespace/case normalization; preserve objects, order and source text. Reuse the same grounding logic in corpus checks. This verifies quote presence, not meaning, correct speaker attribution or whether a request was withdrawn.
3. **4.3 — LLM helper:** implemented: LangChain/OpenAI, validated env settings, token/cost accounting, budget admission/overrun checks, disabled SDK retries, unknown-cost blocking, optional LangSmith tracing and sanitized errors.
4. **4.4 — Extraction:** implemented: real `START → extract → END` LangGraph, structured output, Pydantic validation, duplicate-ID rejection and grounding. CLI returns requirements, drops, usage, latency and trace URL. Real run succeeded.

Add Story and RunResult contracts when their first consumer is implemented, before exposing corresponding API payloads. Do not prebuild unused models in step 4.1.

Step 4.1 verification: 24 tests passed, including contract validation of all 29 gold requirements; Ruff lint and format checks passed. No LLM, prompt, model, Docker or database integration was changed. Manual practice is in the README Requirement contract section. Review confirmed one shared contract rather than repeated enum rules, strict inputs, quote preservation and independent reference lists.

Step 4.2 verification: 36 tests passed, including 12 grounding checks and all 29 gold quotes across 12 cases. Ruff lint and formatting passed. Tests cover normalization, empty/invented quotes, disconnected words, punctuation differences, original object/order preservation, and empty or fully unsupported results. The README console exercise expects True/False/False. No dependencies, LLM calls, Docker settings or database integration changed.

- Deliverable: Pydantic models, an LLM helper with cost tracking and budget enforcement, structured output, `extract`, and the grounding filter.
- Checks: valid/invalid model outputs, exact quotes under whitespace/case normalization, empty/invented quotes, provider errors, and budget exhaustion. Use provider substitutes in tests and perform one real run when a key is available.
- Manual acceptance: inspect extracted requirements, verify every quote in one transcript, and inspect run cost.
- Done when: contracts pass, post-filter grounding is 1.0 on the checked sample with N reported, and a real run is confirmed.

Final phase 4 verification: **63 tests pass**, Ruff lint/format pass. Offline HTTP tests exercise the real LangChain structured client and LangGraph: invalid output, accounting, budget rejection/overrun, provider errors without retries, unknown usage, duplicate IDs and enabled tracing failures. Independent standards/spec reviews found path portability and tracing-result-loss defects; both were fixed, including bounded flush/close.

Real smoke evidence (2026-11-02): run `7c3f88ee-e9d6-4a9a-bc4d-cb2c7c8746c2`, transcript `01-exports.md`, 4 retained/grounded requirements, 798 input / 253 output tokens, estimated $0.004632, 3983 ms. LangSmith retrieval confirmed root name `requirement_extraction` and status `success`. Two paid smoke calls totalled estimated $0.008286. No full-corpus LLM recall, precision, F1 or judge score is claimed. User review of requirements and the saved trace remains pending.

## Phase 5. RAG and classification

**Status:** in progress. Original items 1.4 and 1.6. The user chose Neon (cloud Postgres with pgvector) instead of waiting for local Docker on 2026-11-02.

1. **5.1 — chunking:** implemented in `app/rag/chunking.py`. One chunk per `## ` heading, ID taken from the stable `HD-*` prefix (slug otherwise), text before the first heading becomes `intro`. Sections over 2000 characters are packed by paragraph into `ID#1`, `ID#2`; an oversized paragraph is cut at fixed offsets. Harbor Desk yields 13 chunks covering every gold reference.
2. **5.2 — ingestion:** `app/rag/ingest.py` creates the extension and `spec_chunks` table, embeds through the shared helper (`text-embedding-3-small`, cost accounted) and replaces a project's chunks in one transaction under an advisory lock. Unchanged text and model skip embedding entirely.
3. **5.3 — retrieval:** `retrieve(conn, helper, project_id, queries, k=5)` embeds all queries in one call and orders by cosine distance. Refuses a project that is not ingested instead of returning nothing.
4. **5.4 — `retrieve_spec` + `classify`:** graph is `extract → retrieve_spec → classify` when a project is given. One LLM call classifies all requirements; code rejects missing/extra IDs, references to chunks that were not retrieved, and duplicate/conflict without a reference.
5. **5.5 — measurement:** `evals/run_evals.py` runs retrieval and classification on the 29 gold requirements (extraction is bypassed so errors are attributed to this phase). Reports recall@5, status accuracy and conflict F1 with N; no thresholds until phase 10.

Verification (2026-11-02, Neon `discovery` database): 72 tests pass offline plus the live database test (10/10 in `test_rag.py` with `TEST_DATABASE_URL`); Ruff lint/format pass. Ingestion stored 13 chunks for 2,397 embedding tokens (~$0.00005); a second run reported `changed: false` at zero cost. Query "Can coordinators export reports?" returned `HD-EXPORT` first (distance 0.415). Full run on `01-exports.md`: 3 calls, $0.0131, 7.8 s, LangSmith trace URL returned; coordinator export classified `conflict` → `HD-EXPORT`, monthly count wrongly `conflict` (gold `new`).

The first full run was blocked by the budget admission check because every requirement repeated its excerpts; excerpts are now sent once and referenced by ID.

Evals on gold requirements (extraction bypassed), N=29:

| Prompt | Recall@5 | Status accuracy | Conflict F1 | Cost |
|---|---|---|---|---|
| v1 | 0.97 | 0.83 | 0.67 (tp 5, fp 5, fn 0) | $0.068 |
| v2: "outside baseline / not approved" means new | 0.97 | 0.90 | 0.77 (tp 5, fp 3, fn 0) | $0.068 |

Remaining misses: `05-usability R2`, `07-new-preset R1` (spec says presets are not persisted; gold says new) and `06-operations R1` (public status page judged against `HD-ACCESS`; `HD-OPERATIONS` not in top 5, the only retrieval miss). Prompt tuning stopped here to avoid fitting 29 examples; the user decides whether these are model or gold errors. Runs are single samples, not averaged.

- Deliverable: heading-based specification chunking with a fixed-size fallback, embeddings in pgvector, `retrieve(query, k=5)`, `retrieve_spec`, and `classify` with chunk references.
- Checks: chunking, repeated ingestion, retrieval recall@5, labels against gold cases, and stored database data. Run evals for modified prompts/models.
- Manual acceptance: follow requirement → status → specification excerpt, including a planted conflict.
- Done when: retrieval is measured with N, references exist, and a person checks classifications. Final shared quality thresholds are recorded in phase 10.

## Phase 6. Stories and critic

**Status:** not started. Original item 1.7.

- Deliverable: `write_stories`, testable acceptance criteria, open questions, requirement links, and a `critic` with at most one revision cycle.
- Checks: story contracts, requirement references, stable idempotency keys, critic-loop bounds, and evals for prompt changes.
- Manual acceptance: trace a story to its requirements and determine whether its acceptance criteria can actually be executed.
- Done when: stories pass checks and the user accepts their structure.

## Phase 7. Human review and Jira

**Status:** not started. Original item 1.8.

- Deliverable: assembled LangGraph, Postgres checkpointer, `human_review` interrupt, resumption only after Approve, and `create_tickets` with dry-run and real Jira support.
- Checks: no writes before Approve; human edits are validated and reach the preview; state survives restart; repeated/concurrent approvals do not duplicate tickets; handle 429/5xx and ambiguous create results.
- Manual acceptance: pause at review, restart the API, edit a story, approve it, and repeat approval without duplicates.
- Done when: the dry-run workflow is accepted. Verify real Jira separately in a test project when access is available; explicitly record if that verification has not happened.

## Phase 8. API, SSE, and observability

**Status:** not started. Original item 1.9.

- Deliverable: `/projects`, run creation/state, SSE, approval endpoint, error events, cost, latency, and trace URL. One full run must be visible in LangSmith.
- Checks: API integration workflow, input validation, unknown runs, event ordering, SSE reconnection/final-state retrieval, and repeated approval.
- Manual acceptance: complete the workflow through the API and open its matching trace.
- Done when: API processing reaches a preview, errors are visible, and the trace matches the run.

## Phase 9. Interface

**Status:** not started. Original items 2.1–2.5.

- Deliverable: Next.js project/transcript selection and text input, live timeline, requirements table, highlighted quotes/spec refs, story editor, Approve, and Jira preview. Include retrieved chunks, cost, latency, and trace URL in the detail panel.
- Checks: TypeScript strict mode, ESLint, build, main browser workflow, loading/error states, and keyboard operation. Split screens into individually accepted steps if needed.
- Manual acceptance: without a terminal, choose a transcript, inspect a conflict, edit a story, approve, and inspect the preview.
- Done when: the browser workflow works and the user accepts it.

## Phase 10. Measured quality

**Status:** not started. Original item 2.6. Introduce the runner earlier as soon as there is model behavior to evaluate.

- Deliverable: complete `evals/run_evals.py`, LangSmith dataset, baseline, saved thresholds, and a CI subset that fails below threshold. Calibrate the LLM judge on ten manual scores.
- Checks: 12+ gold cases; grounding 1.0; precision/recall and conflict F1 at least baseline − 0.05; story quality at least 3.5/5. An intentionally poor result must produce a nonzero exit code. Cost and p95 latency are report-only metrics.
- Manual acceptance: examine concrete mistakes and confirm the metrics reflect quality rather than merely output format.
- Done when: actual metrics with N are published in README and the user accepts the baseline and thresholds. Never invent numbers before measurement.

## Phase 11. Deployment and demonstration

**Status:** not started. Original items 2.7–2.8.

- Deliverable: Neon, Docker API on Render, web on Vercel, preset cache, daily LLM budget, public dry-run, GIF, verified commands, architecture, and `docs/case-study.md`.
- Checks: production smoke test, persistence across restarts, budgets, no public Jira writes, and timed main workflow.
- Manual acceptance: a new visitor opens the URL without registration, runs a preset, sees quotes and a conflict, edits a story, approves it, and receives a preview in under two minutes.
- Done when: the workflow is accepted and README contains its URL and measured results. Configure access, pricing choices, and secrets before deployment.
