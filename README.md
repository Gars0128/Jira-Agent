# Discovery → Jira Agent

> From a messy client call to reviewed Jira tickets in 2 minutes — every requirement traced back to the transcript.

We are building a web application that turns a client-call transcript into human-reviewed Jira user stories. It extracts requirements, links them to quotes, compares them against the project specification, exposes contradictions, and drafts tickets with acceptance criteria. A person reviews the result and decides what to send to Jira.

**Status:** phase 1, API step 2.1 and phase 3 demo data are accepted. Phase 4 has started with the Requirement contract; step 4.1 awaits manual review. Docker step 2.2 is deferred and the first remote CI run remains unverified. There is no AI analysis or deployed demo yet. Two minutes is the target workflow duration, not a measured result.

The sections below describe the **whole target product**. Phased development gradually implements this complete workflow.

## Who it helps and why

After a discovery call, an analyst, PM, or engineer must separate requirements from discussion, compare them with existing agreements, and turn the result into actionable tickets. Conversations contain small talk, vague requests, changes of mind, and contradictions that are easy to lose in manual notes.

Our result is a verifiable chain: **transcript statement → requirement → specification comparison → story → approved ticket**. The application supports the decision; a human makes the final call.

The project also demonstrates discovery, AI engineering, and full-stack skills to a hiring manager: RAG, LangGraph, structured model output, evaluations, tracing, cost controls, reliable integration, and a usable interface.

## Complete workflow: input to result

### 1. Open the demo and choose inputs

A visitor opens the site without registering, chooses a fictional project, sees its description and specification, and selects one of six transcripts or pastes text without real client data.

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

A critic reviews the drafts and can request revision at most once. Execution then pauses for **human review**. A confidently written story must not hide an unresolved decision.

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
                                        ↑             │
                                        └─ revision ──┘  at most once

critic → human_review [wait for Approve] → create_tickets
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

**We will learn LangChain and LangGraph separately.** LangChain provides model, tool, and agent components and integrations. LangGraph manages graph execution and state and can be used without LangChain. LangGraph is required by our plan; specific LangChain components will be selected when implementing integrations. Start with the official [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) and [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview).

## MVP scope and definition of done

The MVP includes one fictional project, a specification of roughly five pages, six transcripts with changes of mind and 3–4 planted conflicts, at least 12 labeled eval cases, the full UI workflow, and deployment. Audio, authentication, multiple users, Linear/Trello, story points, real client data, and an elaborate design system are out of scope.

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

The baseline follows the first real evaluation. No model-quality metrics have been measured, and there is no deployed demo. Add GIF and case study after a working implementation. Checks on fixture structure and quotes do not measure model precision, recall, or story quality.

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

Each phase uses small steps. The agent explains inputs, code, and expected outputs, implements the step, runs checks, and provides reproducible manual instructions. The user tries them, asks questions, and confirms progression. Passing tests alone does not close a phase. The earlier two-agent CI/demo-data and translation batch is finished; work has returned to sequential steps.

## Current status and local development

Phase 3 demo data is accepted and phase 4 has started. The API still has only `/health`; the new Requirement model validates data in Python and tests, with no extraction endpoint or LLM call yet. Docker is deliberately deferred, and remote CI execution is unverified. See the [plan](docs/plan.md) for current checkpoints. Phases 5–11 have not started.

### Run the API without Docker

You need Python to invoke [uv](https://docs.astral.sh/uv/getting-started/installation/). These commands use uv as a Python module; if absent, install it with `python -m pip install uv`. uv installs Python 3.12 if unavailable and creates `.venv` inside `apps/api`. The first setup requires internet access. `uv.lock` fixes dependency versions.

From the repository root in PowerShell:

```powershell
cd apps/api
python -m uv sync --locked
python -m uv run uvicorn app.main:app --reload
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

All collected tests must pass, Ruff must report no errors, and no files should require formatting. Step 4.1 reports 24 passing tests: health, corpus integrity, corruption checks, and the Requirement contract.

**What happens:** the browser sends `GET /health`. FastAPI calls `health` in `apps/api/app/main.py` and serializes the returned Python dictionary as JSON. An endpoint is a request-handler address. `TestClient` checks the HTTP status and response without starting a separate server. `/health` currently proves API liveness, not database or AI readiness.

### Requirement contract: step 4.1

[`Requirement`](apps/api/app/schemas.py) defines the fields accepted by later extraction and classification steps. It rejects blank required strings, invalid types/enums and unknown fields. Before classification, `status` defaults to null and `spec_refs` to an independent empty list. Quote text is preserved exactly. Validating this model does not prove that a quote occurs in the transcript; grounding is the next step.

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

### CI and demo-data review

The CI workflow at [`.github/workflows/api.yml`](.github/workflows/api.yml) runs locked dependency installation, pytest, Ruff checks, and formatting on pushes and pull requests. It needs no LLM keys or Docker. Its commands pass locally; remote execution must be verified in GitHub Actions after the changes are pushed and has not been observed yet.

The fictional demo project is `harbor-desk`: an equipment-reservation portal used as input for Discovery → Jira. We are not implementing that portal. Its [baseline specification](data/demo/harbor-desk/spec.md), six transcripts, and 12 gold JSON cases provide reference inputs and expected analysis results. Six cases reference transcript files; six synthetic cases include inline transcripts. Specification references use stable `HD-*` heading IDs until runtime chunking is implemented.

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

The API receives `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and `PGPASSWORD`, but it does not execute SQL yet. Application database integration comes with the first storage/search feature. `JIRA_DRY_RUN=true` is passed as a safe container setting; the Jira client is not implemented.

## Documentation map

| Document | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Shared agent rules, checks, and phase boundaries |
| [CLAUDE.md](CLAUDE.md) | Claude Code entry point for the shared instructions |
| [Specification](docs/spec.md) | MVP scope, architecture, contracts, and quality requirements |
| [Phased plan](docs/plan.md) | Implementation order, checks, and manual acceptance |
| [Decision log](docs/decisions.md) | Decisions and their reasons |
