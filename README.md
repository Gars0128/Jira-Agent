# Tiro

*Named after Marcus Tullius Tiro, Cicero's secretary, who invented shorthand to record speech word for word.*

> From a messy client call to reviewed Jira tickets in 2 minutes — every requirement traced back to the transcript.

We are building a web application that turns a client-call transcript into human-reviewed Jira user stories. It extracts requirements, links them to quotes, compares them against the project specification, exposes contradictions, and drafts tickets with acceptance criteria. A person reviews the result and decides what to send to Jira.

**Status:** the local workflow includes extraction, Neon-backed RAG, stories, a bounded critic, persisted approval, Jira previews, HTTP/SSE, and Next.js/TypeScript. Automated and live database checks pass; the full model-quality gate does not yet pass. Manual acceptance is tracked in the [plan](docs/plan.md). Docker and deployment remain deferred.

The sections below describe the **whole target product**. Phased development gradually implements this complete workflow.

## Run the complete application locally

![Recorded local dry-run workflow (earlier UI, before the app-bar redesign)](docs/demo/demo.gif)

Latest review: backend automated checks, isolated Neon persistence/concurrency
checks, seven frontend unit checks and four browser checks passed. Ruff, ESLint,
TypeScript and the web production build passed. The local exports smoke reached
review in 17.3 seconds at approximately $0.019; cached analysis used zero model
calls. These functional checks do not replace the failed model-quality evaluation.

Preserve existing keys in the ignored root `.env`. Configure a direct Neon
`DATABASE_URL` with SSL, the existing OpenAI model/prices, and these user-approved
development limits:

```dotenv
MAX_COST_PER_RUN_USD=0.30
DAILY_BUDGET_USD=1.00
PUBLIC_DEMO=true
JIRA_DRY_RUN=true
```

The daily budget reserves the per-run maximum before admitting work, settles
known usage, and retains unknown-cost reservations. Provider billing can differ
from configured estimates. Public mode always returns previews; Jira keys are
unnecessary.

First terminal, from the repository root:

```powershell
cd apps/api
python -m uv sync --locked
python -m uv run --env-file ../../.env python -m app.rag.ingest ../../data/demo/harbor-desk/spec.md
python -m uv run --env-file ../../.env uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/ready> once. It initializes the run store/checkpointer
and starts the persisted-run worker. `/health` proves liveness; `/ready` also needs
valid configuration and database access. Unchanged ingestion skips embeddings.

Second terminal, from the repository root; use Node 24:

```powershell
cd apps/web
npm.cmd ci
$env:API_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

Open <http://localhost:3000>, select the exports preset and run analysis. Inspect
coordinator export as a conflict with `HD-EXPORT` evidence, review stories, edit
a criterion, and approve to obtain previews. Repeat approval and restart the API
while awaiting review to check persistence and duplicate protection. The server
validates edits and recomputes idempotency keys. Eligible repeated presets reuse
cached analysis before review; its key includes transcript, specification, model
and workflow code.

Three classification disagreements remain in the 29-requirement sample. A missing
story can reflect classification; inspect evidence and questions before approval.
The [case study](docs/case-study.md) records measured results and evaluation limits.
The later 12-case full run **did not meet the quality gate**: precision 0.344,
recall 0.379, conflict F1 0.286 and one rejected evidence reference. Matching and
gold annotation need human review; the working local interface does not establish
production model quality. Seven real judge scores remain uncalibrated. That run predates the critic-once and jokes/deferred-idea extraction changes; quality with the current prompts is unmeasured.

Checks from `apps/api`: `python -m uv run --locked pytest`,
`python -m uv run --locked ruff check . ../../evals`, and
`python -m uv run --locked ruff format --check . ../../evals`.
From `apps/web`: `npm.cmd run lint`, `npm.cmd run typecheck`, `npm.cmd test`,
and `npm.cmd run build`. These checks make no paid model calls.

## Deploy and verify

Deployment is deferred by the user. These are preparation instructions for later;
current acceptance focuses on tests and the local interface.

The root `render.yaml` describes the Docker API; supply private environment values
in Render and preserve public dry-run. Its Docker context is the repository root
to include fictional demo assets. In Vercel choose root `apps/web`, Node 24, and
set server-side `API_URL` to the Render HTTPS URL **before building**. Keep keys
and database URLs out of `NEXT_PUBLIC_*` variables.

Ingest the deployed specification, check readiness, and perform the whole browser
workflow including edited approval, restart recovery, cache and budget rejection.
Record the public URL, actual duration and GIF after these checks. Hosting,
real Jira writes, and the calibrated quality gate remain separately verifiable
acceptance work.

## Who it helps and why

After a discovery call, an analyst, PM, or engineer must separate requirements from discussion, compare them with existing agreements, and turn the result into actionable tickets. Conversations contain small talk, vague requests, changes of mind, and contradictions that are easy to lose in manual notes.

Our result is a verifiable chain: **transcript statement → requirement → specification comparison → story → approved ticket**. The application supports the decision; a human makes the final call.

The project also demonstrates discovery, AI engineering, and full-stack skills to a hiring manager: RAG, LangGraph, structured model output, evaluations, tracing, cost controls, reliable integration, and a usable interface.

## Complete workflow: input to result

### 1. Open the demo and choose inputs

A visitor opens the site without registering, chooses "Harbor Desk (with specification)" or "Any conversation", and selects a sample transcript or pastes fictional text. Without a specification, statuses are only new or unclear and conflicts are not checked.

The specification contains existing agreements. The transcript introduces requests to compare against them. The MVP does not support uploading another specification through the UI; analysis uses the selected demo project.

### 2. Run the analysis and watch progress

After **Run**, the UI shows requirement extraction, specification retrieval, classification, story drafting, and critic review. SSE events from the API show progress and any error.

### 3. Check requirements and evidence

A requirements table shows text, type, priority, speaker, quote, and status. Selecting a requirement highlights its quote in the transcript. Code discards requirements without a verified quote.

The application retrieves relevant specification chunks and assigns a status:

| Status | Meaning for the reviewer |
|---|---|
| `new` | A new requirement relative to the retrieved agreements |
| `duplicate` | Already described in the specification |
| `conflict` | Contradicts the specification; the difference needs review |
| `unclear` | Insufficient information for a confident decision; clarification is needed |

Retrieved specification excerpts make the classification inspectable. Each status is an agent judgment that a person can check against the source texts.

### 4. Review stories and open questions

The agent drafts stories in the form “As a …, I want …, so that …” with testable acceptance criteria, preferably Given/When/Then. Stories reference their source requirements. A separate list holds questions to return to the client, including unresolved conflicts.

A critic reviews the drafts once and can request one revision; the revision goes straight to **human review** without a second critique. A confidently written story must not hide an unresolved decision.

### 5. Edit and approve

The reviewer edits stories and acceptance criteria. No Jira tickets are created before **Approve**. The server validates the edits before resuming the saved run.

### 6. Receive a Jira preview or created tickets

The public demo always uses **dry-run**: it previews the tickets that would be created without writing to Jira.

In a separately configured real-Jira mode, approval creates tickets and returns their links. Repeated approval must not create duplicates. Temporary API errors receive bounded retries.

### 7. Inspect what happened

The **Under the hood** panel shows retrieved specification chunks, run cost, latency, and a LangSmith trace link. This makes the path from source text to result visible and helps investigate mistakes.

## What the interface should contain

These areas form one connected workflow. We will agree on the exact layout during UI implementation.

| Area | Contents |
|---|---|
| Inputs | Project, transcript picker, transcript text, Run button |
| Progress | Step timeline, current status, and error messages |
| Requirements | Status table, highlighted quotes, related specification excerpts |
| Human review | Stories, acceptance-criteria editor, questions, Approve button |
| Result | Jira preview or links to created tickets |
| Under the hood | Retrieved chunks, cost, latency, and trace URL |

## One example from start to finish

This is an illustration using fictional data, not an accepted demo fixture:

- Specification: “Report exports are available to administrators only.”
- Transcript: “Exports should now be available to managers too.”
- The agent extracts the requirement, preserves the quote, retrieves the restriction, and shows `conflict`.
- Open question: “Do we approve expanding report-export access to managers?”
- Draft story: “As a manager, I want to export a report so that I can share it with colleagues.” Example criterion: “Given approved manager access, when the manager exports a report, then a report file is returned.”
- The reviewer checks the difference, adjusts the story after clarifying the decision, and clicks Approve. The public demo returns a ticket preview.

The example shows why both evidence and human approval are necessary.

## What the agent does internally

One analysis is one **run** with shared state: source text, requirements, retrieved chunks, stories, questions, cost, and execution status.

```text
extract → retrieve_spec → classify → write_stories → critic
                                        ↑             │ issues (once)
                                        └─ revision ──┘

critic (no issues) or revision → human_review [wait for Approve] → create_tickets
```

| Step | Input → output |
|---|---|
| `extract` | Transcript → structured requirements; code removes unverified quotes |
| `retrieve_spec` | Requirements → relevant specification chunks from pgvector |
| `classify` | Requirements and chunks → statuses, chunk references, and explanations |
| `write_stories` | Checked requirements → stories, acceptance criteria, and questions |
| `critic` | Drafts → review findings and at most one revision request |
| `human_review` | Prepared result → saved pause for a person to review |
| `create_tickets` | Approved stories → dry-run preview or Jira tickets |

A Postgres checkpointer persists graph state so execution can resume after a restart. Every LLM call records token usage and cost; exceeding the budget ends the run with an error.

## Architecture and technology roles

```text
Browser: Next.js / Vercel
    │ POST /runs, GET state, POST approve
    ↓                         ↑ SSE: execution events
FastAPI + LangGraph / Docker on Render
    ├─ Postgres + pgvector / Neon: chunks and checkpoints
    ├─ LLM API: extraction, classification, stories, embeddings, judge
    ├─ LangSmith: traces and eval datasets
    └─ Jira Cloud REST API v3: only after Approve
```

| Technology | Its role |
|---|---|
| Next.js, TypeScript, Tailwind | Input, review, and editing UI |
| FastAPI, Python 3.12 | HTTP API and processing entry point |
| LangGraph | Explicit steps, transitions, state, pauses, and resumption |
| RAG | Retrieve relevant source excerpts before the model answers |
| Embeddings and pgvector | Represent text as vectors and find related excerpts |
| Pydantic | Validate requirements, stories, and request structure |
| LangSmith | Inspect execution and evaluate the agent |
| Jira API | Create approved tickets in the configured real-write mode |

**LangChain and LangGraph are separate parts of the implementation.** Phase 4 uses `langchain-core` messages and `langchain-openai` for model calls. LangGraph manages state and the full workflow graph shown below. Start with the official [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) and [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview).

## MVP scope and definition of done

The MVP includes one fictional project with a specification of roughly five pages, an "Any conversation" mode without a specification, six transcripts with changes of mind and 3–4 planted conflicts, at least 12 labeled eval cases, the full UI workflow, and deployment. Audio, authentication, multiple users, Linear/Trello, story points, real client data, and an elaborate design system are out of scope.

We check completion in two ways:

1. **Working workflow:** a new visitor opens the Vercel URL without registration, runs a preset, inspects a grounded requirement and conflict, edits a story, approves it, and receives a preview in less than two minutes.
2. **Measured quality:** evals run against labeled cases; README reports actual values with sample size N, cost, and latency. CI fails changes that fall below thresholds.

| Check | Target |
|---|---|
| Grounding rate | 1.0 after filtering; an empty result is not evidence of quality |
| Requirement precision / recall | At least the fixed baseline − 0.05 |
| Conflict detection F1 | At least the fixed baseline − 0.05 |
| Story quality | Mean ≥ 3.5/5; judge calibrated on 10 manual scores |
| Cost/run and p95 latency | Measure and report; configure numeric budgets during implementation |

The fixed phase-5 sample measured retrieval recall@5 **28/29 (0.966)**, status accuracy **26/29 (0.897)**, and conflict F1 **0.769** (TP 5, FP 3, FN 0), at approximately **$0.068**. Extraction was bypassed: this is not an end-to-end baseline. Full precision/recall and ten manual judge ratings remain to be reviewed. See the [case study](docs/case-study.md); no public deployment is claimed.

## How we will build and learn

| Phase | Deliverable |
|---|---|
| 1. Instructions and plan | Complete workflow, working rules, and acceptance criteria |
| 2. Local scaffold | API `/health`, Docker, Postgres, and CI |
| 3. Demo data and gold labels | Specification, transcripts, and 12+ labeled cases |
| 4. Extraction | Contracts, first LLM call, quoted requirements, and cost |
| 5. RAG and classification | Specification retrieval and conflict detection |
| 6. Stories and critic | Stories, criteria, questions, and bounded revision |
| 7. Human review and Jira | Full graph, persistence, approval, preview, and Jira client |
| 8. API and observability | Runs, SSE, errors, and a LangSmith trace |
| 9. Interface | Complete browser workflow |
| 10. Quality | Evals, baseline, thresholds, and quality gates in CI |
| 11. Deployment | Public demo, budget, cache, GIF, and case study |

The [detailed plan](docs/plan.md) preserves the original scope and lists checks, manual acceptance, and learning exercises for each phase. The original two-day estimate does not limit our learning pace.

The user authorized phases 6–11 together with parallel agents. Implementation still uses explicit contracts, checks and persisted checkpoints. Passing tests does not replace manual acceptance; the user can return to individual learning exercises below.

## Current status and local development

Use the complete-application instructions above for the current workflow. The following sections preserve earlier learning exercises. Docker remains deferred; remote CI execution requires separate verification. See the [plan](docs/plan.md) for the current checkpoint.

### Run the API without Docker

You need Python to invoke [uv](https://docs.astral.sh/uv/getting-started/installation/). These commands use uv as a Python module; if absent, install it with `python -m pip install uv`. uv installs Python 3.12 if unavailable and creates `.venv` inside `apps/api`. The first setup requires internet access. `uv.lock` fixes dependency versions.

From the repository root in PowerShell:

```powershell
cd apps/api
python -m uv sync --locked
python -m uv run --env-file ../../.env uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/health>. Expect HTTP `200` with:

```json
{"status":"ok"}
```

Open <http://127.0.0.1:8000/docs> to call `GET /health` through the interactive documentation. Stop the server with `Ctrl+C`.

In another terminal, starting at the repository root:

```powershell
cd apps/api
python -m uv run pytest
python -m uv run ruff check .
python -m uv run ruff format --check .
```

All collected tests must pass, Ruff must report no errors, and no files should require formatting. Phase 4 reports 63 passing tests, including offline HTTP integration through the real LangChain client and LangGraph, cost/error behavior and LangSmith failure handling. Tests need no real keys or paid calls.

**What happens:** the browser sends `GET /health`. FastAPI calls `health` in `apps/api/app/main.py` and serializes the returned Python dictionary as JSON. An endpoint is a request-handler address. `TestClient` checks the HTTP status and response without starting a separate server. `/health` currently proves API liveness, not database or AI readiness.

### Requirement contract: step 4.1

[`Requirement`](apps/api/app/schemas.py) defines the fields accepted by later extraction and classification steps. It rejects blank required strings, invalid types/enums and unknown fields. Before classification, `status` defaults to null and `spec_refs` to an independent empty list. Quote text is preserved exactly. Validating this model does not prove that a quote occurs in the transcript; the separate grounding helper checks that.

From `apps/api`, start a Python console:

```powershell
python -m uv run python
```

Paste this example to load the first accepted gold requirement:

```python
import json
from pathlib import Path
from app.schemas import Requirement

case = json.loads(Path("../../evals/cases/01-exports.json").read_text(encoding="utf-8"))
payload = case["requirements"][0]
requirement = Requirement.model_validate(payload)
print(requirement.status)
print(requirement.quote)
```

Expect `conflict` and the coordinator-export quote from the case. Now deliberately supply a priority outside the agreed vocabulary:

```python
payload["priority"] = "urgent"
Requirement.model_validate(payload)
```

Expect `ValidationError` identifying `priority`; only `must`, `should`, and `could` are allowed. This modifies a dictionary in the console, not the fixture file. Leave the console with `exit()`. No server, Docker, database or API key is needed. To run only the contract tests, use `python -m uv run --locked pytest tests/test_schemas.py`.

### Quote grounding: step 4.2

[`is_quote_grounded`](apps/api/app/grounding.py) checks whether a nonempty quote occurs in the transcript after casefolding and collapsing whitespace. Punctuation and wording must still match. `filter_grounded_requirements` applies this rule to a list of validated Requirement objects, returning grounded items in their original order without modifying their fields. Empty requirements return an empty list; an empty transcript cannot support any requirement.

From `apps/api`, run `python -m uv run python`. At the `>>>` prompt, paste:

```python
from app.grounding import is_quote_grounded

transcript = "Nora: Export\n  reports."
print(is_quote_grounded("EXPORT reports.", transcript))
print(is_quote_grounded("Email reports.", transcript))
print(is_quote_grounded("   ", transcript))
```

Expect `True`, `False`, `False`: the first quote exists despite case/whitespace differences, the second is invented, and the third is empty after normalization. Exit with `exit()`. To run only these tests, use `python -m uv run --locked pytest tests/test_grounding.py`.

The same helper verifies all 29 gold requirements across 12 cases and is connected to the extraction node. Quote presence alone does not prove the requirement's interpretation, its speaker or whether the request was withdrawn. Fixture tests separately verify speaker attribution.

### Real extraction: steps 4.3–4.4

```text
transcript → LangGraph extract node
                 → shared LLM helper → LangChain ChatOpenAI structured output
                 → Pydantic validation → grounding filter
           → requirements, dropped IDs, tokens, cost estimate and trace URL
```

Only six extraction fields are requested from the model. `Requirement` adds `status=null`, `spec_refs=[]` and `note=null`; classification is phase 5. Small talk and withdrawn requests are excluded by the prompt, while vague wishes are retained without invented targets. These are model behaviors to evaluate, not deterministic guarantees of grounding.

Create `.env` in the repository root if absent, preserving existing settings:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Add `OPENAI_API_KEY` locally. Keep model, rates, output limit and budget from `.env.example`, or update the rates when changing model. The example uses `gpt-5.6-terra` at standard text rates of $2 input / $12 output per million tokens, checked on 2026-11-02 against the [official model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra). Model access depends on the account. Never paste keys into chat, commit them or put them in CLI arguments.

For LangSmith, create an external agent through **+ Agent → Observability**, ID `discovery-jira`. Create its API key and configure root `.env`:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-private-langsmith-key
LANGSMITH_AGENT_ID=discovery-jira
LANGSMITH_AGENT_ENVIRONMENT=local
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Do not combine agent addressing with `LANGSMITH_PROJECT`/`LANGCHAIN_PROJECT`. Use your region's endpoint and, if needed, `LANGSMITH_WORKSPACE_ID`. See [agent tracing setup](https://docs.langchain.com/langsmith/log-traces-to-agent). Trace inputs/outputs are hidden; graph steps and accounting metadata remain inspectable. CLI transport logs are suppressed to avoid credential fragments, with generic errors reported instead.

Run from the repository root:

```powershell
cd apps/api
python -m uv sync --locked
python -m uv run --locked --env-file ../../.env python -m app.extract ../../data/demo/harbor-desk/transcripts/01-exports.md
```

The JSON result contains requirements, dropped IDs, calls, input/output tokens, `cost_usd`, `latency_ms`, `run_id`, `trace_url` and `trace_warning`. Settings read process environment; `uv --env-file` explicitly loads the root file. With tracing disabled extraction still works and the URL is null. Errors exit 1 and include available accounting; configuration errors never dump keys or input values.

The helper checks an admission estimate before sending, caps output tokens, disables SDK retries, accounts reported usage before validating output, and aborts on a cost overrun. Transport errors or missing usage set cost to null and block reuse. Configured prices are estimates; cached input is conservatively charged at the full rate. The byte-based admission estimate is not an exact billing cap: an in-flight call can overrun it. Each CLI invocation starts a fresh budget; daily limits are phase 11.

LangSmith URL/flush/close failures cannot discard a completed extraction or replace its primary error. Warnings expose delivery uncertainty; a URL alone is not delivery proof. The pinned SDK's synchronous URL method emits a deprecation warning; migrate it when adopting the async SmithDB runtime API.

Verified smoke test (2026-11-02): one fictional transcript, four grounded requirements, zero drops, 798 input / 253 output tokens, estimated $0.004632, 3983 ms. Server-side LangSmith retrieval confirmed the matching trace status `success`. The first prompt missed the vague performance wish; the revised prompt retained it on rerun. This is one manual smoke case, not a full-corpus recall/F1 baseline. Full model-quality evals remain phase 10.

### RAG and classification: phase 5

```text
spec.md → chunk by "## HD-*" heading → embed → spec_chunks (pgvector)
requirement text + quote → embed → top-5 chunks by cosine distance
requirements + their chunks → classify (new | duplicate | conflict | unclear)
           → code check: every spec_ref was actually retrieved
```

A **chunk** is one retrievable piece of the spec, here one `##` section. An **embedding** is a list of numbers whose distance reflects meaning, so "coordinators export reports" lands near `HD-EXPORT` without sharing exact words. **Top-k** returns the k nearest chunks; `distance` closer to 0 means more similar.

Create a database in the [Neon console](https://console.neon.tech) (Databases → New database, e.g. `discovery`), open **Connect**, turn connection pooling off and copy the URL. Put it into root `.env` only:

```dotenv
DATABASE_URL=postgresql://user:password@host/discovery?sslmode=require
```

From `apps/api`:

```powershell
python -m uv run --env-file ../../.env python -m app.rag.ingest ../../data/demo/harbor-desk/spec.md
python -m uv run --env-file ../../.env python -m app.rag.retrieve harbor-desk "Can coordinators export reports?"
python -m uv run --env-file ../../.env python -m app.extract ../../data/demo/harbor-desk/transcripts/01-exports.md --project harbor-desk
python -m uv run --env-file ../../.env python ../../evals/run_evals.py
```

Expect: ingestion reports 13 chunks and `changed: true`, then `changed: false` on a second run with zero cost. Retrieval puts `HD-EXPORT` first. The full run gives every requirement a `status`, `spec_refs`, `note` and its `retrieved` chunks; R1 (coordinator export) should be a `conflict` citing `HD-EXPORT`. The eval prints recall@5, status accuracy and conflict F1 with N, plus each mismatch. The database test runs only when `TEST_DATABASE_URL` is set.

### CI and demo-data review

The CI workflow at [`.github/workflows/api.yml`](.github/workflows/api.yml) runs locked dependency installation, pytest, Ruff checks, and formatting on pushes and pull requests. It needs no LLM keys or Docker. Its commands pass locally; remote execution must be verified in GitHub Actions after the changes are pushed and has not been observed yet.

The fictional demo project is `harbor-desk`: an equipment-reservation portal used as input for Tiro. We are not implementing that portal. Its [baseline specification](data/demo/harbor-desk/spec.md), six transcripts, and 12 gold JSON cases provide reference inputs and expected analysis results. Six cases reference transcript files; six synthetic cases include inline transcripts. Specification references use stable `HD-*` heading IDs until runtime chunking is implemented.

For manual review, compare [the reporting conversation](data/demo/harbor-desk/transcripts/01-exports.md) with [its gold case](evals/cases/01-exports.json) and the `HD-EXPORT` section of the specification. Find the quote asking for coordinator exports: the baseline allows only administrators, so the gold label is `conflict`. The same case includes `new`, `duplicate`, and `unclear` requirements. Then inspect [the mind-change case](evals/cases/11-mind-change.json): the withdrawn SMS suggestion must not become an active requirement.

Gold expected stories are evaluation expectations, not runtime Jira payloads. In these fixtures, only new requirements get expected stories; duplicates do not create extra stories, while conflicts and unclear requests stay open for clarification. This annotation convention does not implement or finalize the runtime story policy.

Run `python -m uv run --locked pytest` from `apps/api` to check the health endpoint, corpus references, nonempty quotes attributed to their speakers, and story links. The corpus checks cover 12 cases and include four deliberate corruption checks. They verify fixture integrity, not model precision/recall, conflict F1, or story quality; no LLM has been evaluated yet.

### Docker and Postgres: deferred step 2.2

**Do not run this setup now.** The user chose to leave the Windows hypervisor disabled. Full diagnostic facts, outstanding checks, and resumption criteria are in the [Docker checkpoint](docs/plan.md#docker-checkpoint-step-22). Do not change host settings or retry Docker without a new request. API tests, CI preparation, and demo-data work can continue without containers.

Keep the following instructions for when the user resumes this step. Docker Desktop must be running Linux containers with Compose v2. Execute from the **repository root**; if the terminal is in `apps/api`, first run `cd ../..`. Stop local Uvicorn with `Ctrl+C` to free port 8000. Port 5432 must also be available.

Create local settings once without overwriting an existing `.env`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
```

The password in `.env.example` is a public example for local development only. `.env` is ignored by Git. Never reuse this password for a deployed database. The first run downloads images and dependencies. Expect two `healthy` services: `api` and `db`.

Check <http://127.0.0.1:8000/health> and <http://127.0.0.1:8000/docs>. Expect the same `{"status":"ok"}` response and interactive documentation. Then open psql, the database SQL console. `discovery` is the default user and database from `.env.example`; replace `-U` and `-d` values if you changed them.

```powershell
docker compose exec db psql -U discovery -d discovery
```

Run these inside psql. The first queries should return version `0.8.7` and distance `0`. The remaining commands create a practice table for the persistence check:

```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';
SELECT '[1,2,3]'::vector <-> '[1,2,3]'::vector AS distance;
CREATE TABLE IF NOT EXISTS infrastructure_check (id integer PRIMARY KEY);
INSERT INTO infrastructure_check VALUES (1) ON CONFLICT DO NOTHING;
\q
```

Check persistence after deleting and recreating the containers:

```powershell
docker compose down
docker compose up -d --wait
docker compose exec db psql -U discovery -d discovery
```

Inside psql, `SELECT * FROM infrastructure_check;` should return row `1`. The practice table is only for this check; afterwards, run `DROP TABLE infrastructure_check;` and exit with `\q`.

Use `docker compose down` to stop; the named volume remains. **Do not add `-v` when preserving data:** it deletes the database volume. Changing `.env` does not change the password of an existing database. Init SQL runs only for an empty volume; an existing database can enable the extension manually with `CREATE EXTENSION IF NOT EXISTS vector;` in psql.

If startup fails, inspect `docker compose ps` and `docker compose logs --tail 50 api db`. An unavailable Engine must be resolved before retrying; a port conflict requires freeing the port. After Python changes, rebuild with `docker compose up --build -d --wait`; the image does not enable autoreload.

**What happens:** Dockerfile defines an image containing Python, dependencies, and application code. A container runs that image. Compose places the API and database on a shared network: the API uses `db:5432`; a host program uses `127.0.0.1:5432`. A named volume stores Postgres files separately from the container. pgvector adds the vector type needed for later RAG work.

The API receives `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD` (or `DATABASE_URL`). `JIRA_DRY_RUN=true` is passed as a safe container setting; live Jira writes from `app/jira/` require `PUBLIC_DEMO=false` and `JIRA_DRY_RUN=false` (`Settings.jira_live`).

## Documentation map

| Document | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Shared agent rules, checks, and phase boundaries |
| [CLAUDE.md](CLAUDE.md) | Claude Code entry point for the shared instructions |
| [Specification](docs/spec.md) | MVP scope, architecture, contracts, and quality requirements |
| [Phased plan](docs/plan.md) | Implementation order, checks, and manual acceptance |
| [Decision log](docs/decisions.md) | Decisions and their reasons |
