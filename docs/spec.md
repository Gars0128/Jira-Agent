# Tiro Specification

Based on the user's instructions dated 2026-11-02. This is the target MVP contract, not a claim that every feature exists. See the [plan](plan.md) for implementation order and current status.

## Goal and scope

The demo turns an unstructured client-call transcript into human-reviewed Jira user stories. The main workflow requires no registration and should take less than two minutes: choose a project and transcript → extract requirements with quotes → compare against the specification → edit stories → Approve → Jira preview.

The project must demonstrate discovery, RAG, LangGraph, structured output, evals with a pass threshold, LangSmith traces, per-run cost, human-in-the-loop, idempotency, retries, and a working Next.js UI.

The MVP includes one fictional client with one specification and six transcripts, an "Any conversation" project (`general`) without a specification whose statuses are only new/unclear, at least 12 labeled eval cases, and a deployed demo. Out of scope: audio transcription, authentication and multi-user support, Linear/Trello, story points, real client data, and an elaborate design system.

## Architecture

- Next.js App Router, TypeScript strict mode, and Tailwind; web hosting on Vercel.
- Python 3.12, FastAPI, and LangGraph; Docker API hosting on Render. Long-running, stateful runs are hosted separately from the web application.
- Postgres with pgvector on Neon: specification chunks and LangGraph checkpoints. Locally, Compose uses the `pgvector/pgvector` image.
- LLM API: phase 4 uses OpenAI via LangChain for extraction, with model and prices in env. Classification, stories, embeddings and judging are later consumers.
- LangSmith: traces, cost, and eval datasets.
- Jira Cloud REST API v3: writes only after human approval.

```text
extract → retrieve_spec → classify → write_stories → critic
                                        ↑             │ issues (once)
                                        └─ revision ──┘

critic (no issues) or revision → human_review [wait for Approve] → create_tickets
```

`human_review` uses LangGraph `interrupt`; resumption is allowed only through `POST /runs/{id}/approve`. Use `langgraph-checkpoint-postgres` so runs survive restarts. The critic runs once and may return stories for one revision, which goes straight to human review.

## Planned repository layout

```text
apps/
  api/
    app/
      main.py
      graph/          # nodes.py, state.py, graph.py
      rag/            # ingest.py, chunking.py, retrieve.py
      jira/client.py  # dry-run and real writes
      schemas.py
      config.py
    tests/
    pyproject.toml
    Dockerfile
  web/
data/demo/<project>/
  spec.md
  transcripts/*.md
evals/
  cases/*.json
  run_evals.py
docs/
  decisions.md
  case-study.md
docker-compose.yml
.env.example
```

Add directories and launch commands with working implementations. Verify operational commands from the documented working directory before publishing them in README.

## Data contracts

Once implemented, the Pydantic models in `apps/api/app/schemas.py` become the source of truth. The agreed minimum contract is:

```python
class Requirement(BaseModel):
    id: str
    text: str
    type: Literal["functional", "non_functional", "constraint"]
    priority: Literal["must", "should", "could"]
    quote: str
    speaker: str
    status: Literal["new", "duplicate", "conflict", "unclear"] | None = None
    spec_refs: list[str] = Field(default_factory=list)
    note: str | None = None

class Story(BaseModel):
    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: list[str]
    requirement_ids: list[str]
    idempotency_key: str
```

Quotes must come from the original transcript without rewriting. Code checks non-empty substring membership after whitespace/case normalization and discards ungrounded requirements. `spec_refs` contains retrieved chunk IDs; `note` explains conflicts or ambiguity. Acceptance criteria must be testable, preferably Given/When/Then.

Step 4.1 implements `Requirement` in `apps/api/app/schemas.py`: strict input types, forbidden unknown fields, and at least one non-whitespace character in IDs, text, quote, speaker and each spec reference. Validation preserves the original strings, including quote whitespace. This contract checks structure only; transcript membership is checked separately by the grounding step. `status` may remain null and `spec_refs` empty before classification. `Story` lives in `app/stories.py` and `RunResult`/`TicketResult` in `app/run_contracts.py`.

Step 4.2 implements `is_quote_grounded` and `filter_grounded_requirements` in `apps/api/app/grounding.py`. They compare casefolded, whitespace-collapsed text and reject empty normalized quotes. The filter accepts validated Requirement objects and preserves them unchanged in input order. It does not assess semantic support, speaker attribution or withdrawal of a request; connecting the filter to extraction is step 4.4.

Steps 4.3–4.4 implement a CLI and LangGraph `START → extract → END`. `ExtractedRequirement` contains the six extraction fields; `Requirement` adds classification fields. `ExtractionOutput` wraps the list for native structured output. The graph validates output, rejects duplicate IDs and grounds quotes. `app/llm.py` owns all model calls and run accounting. Settings read process environment; `uv --env-file` loads root `.env` explicitly.

LangSmith uses native agent/environment addressing with hidden I/O. The LLM wrapper sanitizes errors before tracing. URL/flush/close failures produce generic warnings without losing paid results. SDK retries are disabled. Admission cost is a byte-based estimate, not an external billing guarantee; usage is accounted before output validation, overruns abort and unknown cost blocks subsequent calls.

`idempotency_key` is the SHA-256 of the normalized title and requirement IDs. Define normalization and serialization with tests during implementation. Editing and approval must not bypass validation or create duplicates on repeated requests.

`RunResult` must contain requirements, stories, open questions, status, cost, latency, trace URL, and the Jira/dry-run result. Define its full model in the contracts phase.

## API

| Method and path | Contract |
|---|---|
| `GET /health` | API liveness: HTTP 200 with `{"status":"ok"}`; does not check the database |
| `GET /projects` | List of demo projects |
| `POST /runs` | `{project_id, transcript}` → `{run_id}`; start the graph in the background |
| `GET /runs/{id}` | Current state: requirements, stories, questions, cost_usd, latency_ms, trace_url |
| `GET /runs/{id}/events` | SSE: `node_started`, `node_finished`, `awaiting_review`, `done`, `error` |
| `POST /runs/{id}/approve` | `{stories}` → resume the graph and return tickets or a dry-run preview |

Validate input, story edits, and whether approval is allowed in the current state on the server. Define error formats, preset transcript delivery, and SSE reconnection behavior in the relevant phases.

## Reliability and cost

- Route every LLM call through one helper that records tokens and price. Exceeding `MAX_COST_PER_RUN_USD` terminates the run with an error.
- Write to Jira only from `create_tickets` after Approve. Before creation, check the ledger and search for label `idem-<first 16 hex of key>` and reuse an existing ticket. Issues carry labels `idem-…` and `discovery-agent`; descriptions have sections User story, Acceptance criteria, Source evidence and Related rules from the same call; live results include the issue `url`.
- Retry 429/5xx with exponential backoff, at most three retries after the initial attempt. After an ambiguous create response, check whether the ticket exists before retrying.
- A label lookup alone does not protect against concurrent approvals. Phase 7 must include verified protection against competing writes.
- Default `JIRA_DRY_RUN=true`; public mode always uses dry-run regardless of UI state. Keep secrets in environment variables and out of the repository and logs.
- The public demo needs a preset cache and daily LLM budget.

## Quality evaluation

Data: six labeled transcripts and at least six short synthetic cases. Each contains gold requirements, conflicts, and expected stories. RAG splits the specification by headings with a fixed-size fallback and retrieves the top five chunks; measure recall@5 separately.

| Metric | Method | Criterion |
|---|---|---|
| Requirement precision / recall | Match gold using embedding similarity ≥ 0.8 | Fail below the fixed baseline − 0.05 |
| Grounding rate | Share with verified quotes after filtering | 1.0; an empty result is not evidence of quality |
| Conflict F1 | Compare against gold conflicts | At least baseline − 0.05 |
| Story quality | LLM judge, 1–5: INVEST and testable AC; calibrated on 10 manual scores | Mean ≥ 3.5 |
| Cost/run and p95 latency | LLM helper / LangSmith | Report only |

Set the baseline after the first measurement; do not recalculate it automatically to pass checks. Report every result with N. CI runs a small eval subset on PRs and fails below threshold; prompt or model changes require evals before merge. Add real metrics, GIF, and case study only after verification. Fixture-validation tests are not model-quality evals.

## Final acceptance

A new visitor opens the Vercel URL without registering, runs a preset, sees requirements with quotes and a detected conflict, edits a story, approves it, and receives a Jira preview in less than two minutes. README contains measured eval results with N and per-run cost.
