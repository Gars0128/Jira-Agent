# Decision Log

## 2026-11-02 — Complete remaining implementation with bounded parallel work

**Decision:** the user authorized phases 6–11 together and requested agents.
Assign disjoint workflow, web and evaluation/documentation ownership; integrate
through explicit contracts. Keep phase acceptance and deployment verification
separate. Development limits approved by the user are $0.30/run and $1/day.

**Why:** one complete browser workflow is now more useful than pausing after each
implementation step. Ponytail still selects the smallest complete solution:
Postgres-backed run state/checkpoints/events, one bounded critic revision, public
dry-run, conservative daily reservations and versioned preset caching.

**Limits:** manual judge calibration requires ten real human ratings; a prepared
Render/Vercel configuration is not a deployed demo. Real Jira writes and host
virtualization changes remain outside automatic verification.

## 2026-11-02 — Persist development lessons without a memory framework

**Decision:** read [lessons.md](lessons.md) before work and update it after a
recurring or non-obvious defect, alongside the shared fix and behavioral test.
Keep authoritative phase checkpoints in the plan. Harness has no automatic
error-recording hook in this repository.

**Why:** a small tracked file survives new chats and can point to executable
regressions. More instructions alone do not prevent a broken implementation.

## 2026-11-02 — Shared instructions and phased work

**Decision:** `AGENTS.md` contains the shared Codex and Claude Code rules; `CLAUDE.md` imports it. README explains the whole product, `docs/spec.md` holds the target contract, and `docs/plan.md` records implementation order and acceptance status.

**Why:** the user wants to learn collaboratively, verify each stage manually, and confirm progression. A short instruction file with precise references helps agents find requirements without duplicating the full specification.

**Rejected:** independent instruction sets for each agent, automatically implementing the entire two-day plan, and marking work complete based only on tests.

## 2026-11-02 — Apply tools as needed

**Decision:** choose individual skills for the task while preserving phase boundaries. Full ECC, automatic hooks, and permanent multi-agent operation are not project requirements. Do not copy personal skill collections into the repository.

**Why:** project instructions must work on another computer; an installed toolbox does not require every workflow to run. Ponytail sets the minimum complete scope. Harness ideas provide explicit outputs, checks, checkpoints, and stop conditions.

**Rejected:** requiring every personal plugin before someone can work on the repository.

## 2026-11-02 — Complete README and learning within phases

**Decision:** README independently explains the entire target product from input to Jira preview, including UI, internal workflow, architecture, and acceptance. The detailed plan divides implementation into phases with small manual exercises.

**Why:** the user needs the full picture and an explanation of each step, including unfamiliar LangGraph, LangChain, and RAG concepts. Documentation of the current stage must not replace the final product description.

**Rejected:** a README limited to current work and links; implementing a large phase without intermediate discussion and user practice.

## 2026-11-02 — First API step and reproducible environment

**Decision:** start phase 2 with one `GET /health` endpoint and an HTTP test. Use Python 3.12 through uv, `pyproject.toml`, and a committed `uv.lock`. Runtime dependencies are FastAPI and Uvicorn; development dependencies are pytest, HTTPX2, and Ruff. The installed Starlette version uses HTTPX2 for TestClient and warns that HTTPX is deprecated. README invokes uv as `python -m uv` because the module is installed but `uv` is not on PATH on the current machine.

**Why:** the user can launch the service and verify one clear contract before Docker, the database, or AI. `/health` returns `{"status":"ok"}` and currently checks API liveness only.

**Rejected:** configuring all infrastructure at once, pretending to check a database that is not connected, and using the installed Python 3.13 instead of the agreed Python 3.12.

## 2026-11-02 — Local API and Postgres containers

**Decision:** Compose defines the API and Postgres 17 with pgvector 0.8.7. A named volume stores database files; init SQL enables the vector extension on first database creation. The API image uses uv 0.13.6 and the lockfile without development dependencies, runs as a non-root user, and has a restricted build context.

**Why:** this provides a reproducible local setup without installing Postgres directly on Windows. The database healthcheck and `service_healthy` dependency define startup order; a separate API healthcheck checks HTTP. Ports bind to loopback only. Secrets come from ignored `.env`; separate `PG*` variables avoid manually assembling a URL containing a password.

**Rejected:** adding a SQL driver and pool before application queries exist, storing the database in the container layer, and including `.env` or the local Windows `.venv` in the image. Step 2.2 passes database settings to the API but does not open a SQL connection; `/health` remains a liveness check. Container behavior is still unverified.

## 2026-11-02 — Defer Docker and continue independent work

**Decision:** leave Docker step 2.2 deferred at the user's request. Do not change Windows boot settings or enable the hypervisor. Keep the durable resumption checkpoint in [the plan](plan.md), with a short reminder in `AGENTS.md`.

**Why:** the user confirmed `hypervisorlaunchtype Off`. Firmware virtualization and the WSL/Virtual Machine Platform components are enabled, but the Windows hypervisor is not running. Docker's initial Engine HTTP 500 was followed by its virtualization error. CI and fictional demo data can be prepared without a local database.

**Rejected:** declaring Docker complete after configuration validation, silently provisioning cloud Postgres, adding a separate memory framework, or changing host settings to unblock development.

## 2026-11-02 — English documentation and a bounded parallel batch

**Decision:** maintain one English documentation set and keep user-facing explanations in Russian. For this batch, the user explicitly authorized two agents: one for step 2.3 and phase 3, and another for documentation. Acceptance still requires integration checks and the user's manual review.

**Why:** English makes the portfolio accessible to a wider audience. Independent file ownership lets CI/data work proceed alongside translation without duplicate documentation or conflicting edits.

**Rejected:** maintaining parallel Russian copies, treating delegation as permanent autonomy, or claiming GitHub Actions passed before a remote run has been observed.

## 2026-11-02 — Fictional reference corpus and CI without Docker

**Decision:** use Harbor Desk, a fictional equipment-reservation portal, as input data for Discovery → Jira. Store six conversations and twelve gold cases with stable specification section references. Gold stories cover new requirements; unresolved conflicts and unclear requests remain questions. This annotation convention does not yet define implemented runtime behavior. Check fixture integrity with pytest and run the same checks in the API workflow without Docker or LLM credentials.

**Why:** requirements and contradictions can be reviewed manually before building extraction or RAG. A small-talk-only case and a withdrawn-request case help distinguish product requests from incidental conversation. Corruption checks prove that invalid quotes, speakers, spec references, and story links are rejected.

**Rejected:** implementing the fictional portal, presenting fixture checks as model-quality evals, generating Jira tasks for unapproved policy changes, or closing the deferred Docker checkpoint because independent tests pass.

## 2026-11-02 — Requirement contract before extraction

**Decision:** start phase 4 with one Pydantic Requirement model in `app/schemas.py`. Reject unknown fields, invalid types/enums and blank required strings without trimming quotes. Reuse the model in corpus validation and declare Pydantic as a direct dependency; it is already installed through FastAPI.

**Why:** one executable contract keeps future model output and current gold fixtures aligned. Structural validation needs no provider, credentials, database or network call. Quote membership depends on the transcript and belongs in the next grounding step.

**Rejected:** duplicate enum validation in fixtures, custom parser wrappers, adding unused Story/RunResult models now, or claiming that a structurally valid requirement is grounded.

## 2026-11-02 — Deterministic quote grounding

**Decision:** use casefolding and whitespace collapsing for quote substring checks, reject empty normalized quotes, and return only grounded Requirement objects. Preserve original objects and input order. Reuse the production helper in fixture checks; fixture speaker attribution remains an additional check.

**Why:** the grounding rule is deterministic and testable without an LLM. Exact wording must remain auditable, so do not rewrite quotes, remove punctuation, use fuzzy matching or combine disconnected text fragments to force a match. Normalization affects comparison only.

**Rejected:** another copy of normalization in tests, a model-based judge for quote presence, and treating presence as proof of correct meaning, speaker identity or an active request. Those limitations remain visible during extraction review.

## 2026-11-02 — Full extraction phase with one model boundary

**Decision:** complete phase 4 in the batch requested by the user. Use LangChain/OpenAI, native JSON-schema structured output, six-field extraction records, one LangGraph extract node and a CLI. Extend Requirement from the extraction model so classification fields cannot be invented during extraction. One per-run helper owns requests and accounting, disables retries and blocks further calls after unknown usage or budget exhaustion.

**Why:** this exercises the production libraries without introducing later RAG, HTTP run routes or persistence. Account raw usage before validation so malformed responses are still charged. Configured rates and byte-based admission are estimates, not a strict provider billing cap. Small-talk/retraction handling is prompted behavior, not a grounding guarantee.

**Rejected:** another agent framework, simulated LangGraph, classification fields in extraction output, failed-call cost reported as zero, or a quality baseline inferred from one smoke case.

## 2026-11-02 — Native LangSmith addressing and failure isolation

**Decision:** use the registered agent and local environment, explicitly loaded root env, hidden trace I/O, and sanitized LLM spans with accounting metadata. Catch URL/flush/close failures; bound queue waits. Suppress SDK transport logs only at CLI startup. Independent reviews found and verified fixes for env-path portability and loss of paid results during tracing failures.

**Why:** the user has an agent-based workspace. The real trace was retrieved from the server rather than treating its URL as proof. The user's `.env` was moved from `apps/api` to the root without overwriting another file; keys remain ignored and were not displayed.

**Limit:** pinned LangSmith synchronous URL lookup emits a deprecation warning and is supported until 2027-01-31. Migrate to the async SmithDB URL API with the async runtime. A trace outage must never force repetition of an already paid model call.

## 2026-11-02 — Neon pgvector and phase 5 RAG

**Decision:** use the user's Neon Postgres (pgvector) through one `DATABASE_URL` and psycopg 3; an empty URL falls back to libpq `PG*` variables so Compose keeps working. Chunk by `## ` headings with stable `HD-*` IDs, embed with OpenAI `text-embedding-3-small` through the shared helper, store an untyped `vector` with the model name, and search by exact cosine distance. Re-ingestion replaces a project's rows in one locked transaction and skips embedding when nothing changed. Classification is one structured LLM call per run; references are checked in code against the retrieved chunks.

**Why:** heading IDs equal the gold `spec_refs`, so recall@5 is measurable without a mapping table. Thirteen chunks need no ANN index. The model name column prevents mixing vectors from different embedding models. psycopg is also what the phase 7 Postgres checkpointer uses.

**Rejected:** the `pgvector` Python package and SQLAlchemy (a vector literal is one line), LangChain vector stores (hide the SQL the user wants to learn), an HNSW index for 13 rows, per-requirement classification calls (more cost and latency for the same context), and silently dropping invalid references (hides a model error). Docker step 2.2 stays deferred; Neon does not verify the container.


## 2026-11-02 — No environment auto-tracing

**Decision:** `app.llm` calls `langsmith.configure(enabled=False)` at import. Only explicit `tracing_context(enabled=True)` blocks with hide-input/output clients trace.

**Why:** `uv run --env-file` exports `LANGSMITH_TRACING=true`, so LangGraph `update_state`/resume calls and pytest fakes were auto-traced with the default client, uploading transcript text and test noise.

## 2026-11-02 — Classification refs and Jira descriptions

**Decision:** a classification may cite any excerpt sent in the shared `spec_excerpts` map; cited excerpts are appended to that requirement's evidence. IDs never sent still fail the run. Jira descriptions use ADF sections: user story, acceptance criteria list, and source evidence (requirement, quote, speaker, spec refs, analysis), plus a `discovery-agent` label.

**Why:** excerpts are deduplicated across requirements, so the model legitimately saw neighbouring excerpts; rejecting those refs failed 2 of 6 real transcript runs. Tickets must carry the traceable evidence that the product promises.

## 2026-11-02 — Any-conversation mode

**Decision:** `/projects` adds `general` ("Any conversation"; Harbor Desk is shown as "Harbor Desk (with specification)"). Its search returns no excerpts, so `classify` still runs but may assign only `new` or `unclear`; presets are not cached for it. No document upload yet.

**Why:** users need to split an arbitrary call into stories without a project baseline. Reusing the same graph keeps one workflow. Phase-5 RAG eval after the prompt change matched the baseline exactly (N=29: recall@5 0.966, status accuracy 0.897, conflict F1 0.769). Quality on non-Harbor conversations is unmeasured: there are no gold cases for it.

## 2026-11-02 — Cheaper runs and Jira handoff view

**Decision:** after its single revision, `write_stories` goes straight to `human_review`; the second critique is skipped. Extraction now ignores jokes and ideas explicitly deferred to a later release. After Approve, the UI shows a Jira-style board column whose cards turn from "Creating…" into issue keys with links.

**Why:** the post-revision critique could not change any output and the UI never displayed it, yet it cost a call. On one fictional custom transcript a run dropped from 6 calls / $0.084 / 60 s to 5 calls / $0.055 / 33 s, and a deferred waitlist no longer became a story. Jira pages refuse iframes, so the board is rendered locally.

**Rejected:** `reasoning_effort=low`. One trial broke story constraints (a requirement implemented twice), failing the run. The extraction prompt change is not covered by the RAG eval, which bypasses extraction.

## 2026-11-03 — Product name: Tiro

**Decision:** the user-facing name is Tiro (after Cicero's secretary who invented shorthand to record speech verbatim), shown in the UI, page title, icon, Jira description footer and document titles.

**Why:** "Discovery to Jira" described the function but was not memorable; verbatim capture of a conversation is the product's core promise.

**Unchanged on purpose:** internal identifiers such as the LangSmith agent `discovery-jira`, package names and the Jira label `discovery-agent`, so traces and filters over existing issues keep working.

## 2026-11-03 — Hosted demo is a recorded replay

**Decision:** the public Vercel site (<https://tiro-six-theta.vercel.app>) is built with `DEMO_REPLAY=true`; `/api/*` is rewritten to `app/demo-api`, which replays seven real stored runs (`apps/web/demo/runs.json`) with pipeline timing and returns dry-run previews on approval. Custom text is refused with a pointer to the local setup. Locally `/api` still proxies to FastAPI.

**Why:** the user chose zero hosting cost and no secrets in the cloud over live public analysis. A replay shows the real UI and real outputs without a backend, model spend or load risks (unbounded SSE, long-held run locks).

**Limit:** the hosted demo cannot analyze new text; live hosting (Render API) stays deferred. The replay route is exercised by an end-to-end browser smoke on the deployed site and by `scripts/record-demo.mjs`, not by the CI suite.
