# Learning guide

This is the hands-on companion to the README. The first half has small console
exercises that show one mechanism each. The second half is a route through the
codebase, organised the way an interviewer will ask about it: follow the data,
not the folder tree.

All commands run from `apps/api` unless noted. None of the exercises in part one
needs an API key.

## Part 1. Exercises

### The requirement contract

[`Requirement`](../apps/api/app/schemas.py) is what extraction and
classification agree on. It rejects blank strings, unknown fields and values
outside the enums.

```powershell
uv run python
```

```python
import json
from pathlib import Path
from app.schemas import Requirement

case = json.loads(Path("../../evals/cases/01-exports.json").read_text(encoding="utf-8"))
payload = case["requirements"][0]
print(Requirement.model_validate(payload).status)   # conflict

payload["priority"] = "urgent"
Requirement.model_validate(payload)                 # ValidationError: priority
```

Only `must`, `should` and `could` are allowed. You changed a dictionary in
memory, not the file.

### Quote grounding

[`is_quote_grounded`](../apps/api/app/grounding.py) ignores case and repeated
whitespace, but punctuation and wording must match.

```python
from app.grounding import is_quote_grounded

transcript = "Nora: Export\n  reports."
print(is_quote_grounded("EXPORT reports.", transcript))  # True
print(is_quote_grounded("Email reports.", transcript))   # False: invented
print(is_quote_grounded("   ", transcript))              # False: empty
```

A quote that exists still doesn't prove the interpretation, the speaker, or that
the client didn't take it back two lines later. Evals catch those; code can't.

### One real extraction

```powershell
uv run --env-file ../../.env python -m app.extract ../../data/demo/harbor-desk/transcripts/01-exports.md
```

The JSON shows requirements, dropped IDs, tokens, cost and latency. Run it with
`--env-file ../../.env.ollama` added and it costs nothing.

### Retrieval

```powershell
uv run --env-file ../../.env python -m app.rag.ingest ../../data/demo/harbor-desk/spec.md
uv run --env-file ../../.env python -m app.rag.retrieve harbor-desk "Can coordinators export reports?"
```

Ingest reports 13 chunks, one per `## HD-*` heading. Run it twice: the second
time nothing changed, so it skips the embedding call. Retrieval should put
`HD-EXPORT` first. A smaller distance means closer in meaning.

### Read one labelled case by hand

Open [the exports call](../data/demo/harbor-desk/transcripts/01-exports.md),
its [gold labels](../evals/cases/01-exports.json) and the `HD-EXPORT` section of
the [spec](../data/demo/harbor-desk/spec.md). The spec says only administrators
export reports, and the client asks for coordinators too, so the label is
`conflict`. Then open [the mind-change case](../evals/cases/11-mind-change.json):
the withdrawn SMS idea must not become a requirement.

### Break something on purpose

- In [graph.py](../apps/api/app/graph/graph.py) put the old `raise` back where an
  invalid citation now becomes `unclear`, then run `uv run pytest tests/test_rag.py`.
- In [stories.py](../apps/api/app/stories.py) delete the retry in
  `write_stories` and run `uv run pytest tests/test_workflow.py`.

Both should go red. Undo with `git checkout -- <file>`.

### Docker (deferred on this machine)

Docker isn't set up on the development machine because the Windows hypervisor
is off; [plan.md](plan.md#docker-checkpoint-step-22) has the details. Keep
these steps for when it is. Run them from the repository root with Docker
Desktop on Linux containers, Uvicorn stopped, and ports 8000 and 5432 free.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps                     # api and db both healthy
```

<http://127.0.0.1:8000/health> should return `{"status":"ok"}`. Then check
pgvector and that data survives the containers being recreated:

```powershell
docker compose exec db psql -U discovery -d discovery
```

```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';   -- 0.8.7
SELECT '[1,2,3]'::vector <-> '[1,2,3]'::vector AS distance;    -- 0
CREATE TABLE IF NOT EXISTS infrastructure_check (id integer PRIMARY KEY);
INSERT INTO infrastructure_check VALUES (1) ON CONFLICT DO NOTHING;
\q
```

```powershell
docker compose down
docker compose up -d --wait
docker compose exec db psql -U discovery -d discovery
```

`SELECT * FROM infrastructure_check;` should return `1`. Drop the table
afterwards. Never add `-v` to `docker compose down` unless you mean to delete
the database volume. Changing `.env` doesn't change an existing database's
password, and init SQL only runs on an empty volume. If startup fails, check
`docker compose logs --tail 50 api db`. After Python changes, rebuild with
`--build`, because the image has no autoreload.

Inside Compose the API reaches Postgres at `db:5432`, while programs on your
machine use `127.0.0.1:5432`. The password in `.env.example` is for local use
only.

## Part 2. A route through the code

About four hours. For each stop, read the files, then answer the question out
loud in two minutes without looking. If you can't, read again or ask an agent
to quiz you on that file. Paths are under `apps/api/app/`.

### 1. Run it and break it (30 min)

Run the exports preset locally, find the conflict, edit a story, approve. Then
restart the API while the run waits for review, and click Approve twice.

> **How many model calls does one run make?** Extraction, one embedding call
> for all retrieval queries, classification, story writing, the critic, and
> sometimes a revision. A story-rule break adds one more story call.

### 2. Contracts (20 min): `schemas.py`, `stories.py`, `run_contracts.py`

> **Which fields does the model produce and which does code add?** The model
> writes text, type, priority, quote and speaker, then status, refs and note in
> a separate call. Code adds idempotency keys and the evidence chunks, and
> strips template words like "As a" from story fields.

> **Why Pydantic if the JSON schema is already strict?** The schema guarantees
> shape. Whether IDs match, citations point at excerpts the model actually saw,
> and quotes exist in the transcript, only code can check. So there are three
> layers: syntax, business rules, then quality through evals.

### 3. Extraction and grounding (20 min): `graph/graph.py`, `grounding.py`, `extract.py`

> **Why exact quotes, not fuzzy?** Fuzzy matching lets paraphrase in, and the
> point is the client's own words. The cost is losing a requirement when the
> model changes punctuation. I chose precision over recall for evidence.

### 4. RAG and classification (30 min): `rag/chunking.py`, `rag/ingest.py`, `rag/retrieve.py`, `classify_requirements`

> **Why chunk by heading?** One section is one rule with one ID, and a citation
> should point at a whole rule. Fixed-size chunks cut rules in half, and with
> semantic boundaries there's nothing for an overlap to fix.

> **Why RAG for a 14 KB spec?** Measure it: `run_evals.py --spec-context all`
> gives every requirement the whole spec. On a spec this small long-context may
> be just as good. RAG earns its place with checkable citations and with scale:
> a real client has a spec, a wiki and hundreds of tickets.

> **What happens when one citation is wrong?** That requirement becomes
> `unclear` with a note, and the rest of the run continues. If the model returns
> a different set of IDs, the whole answer is broken and the run fails.

### 5. Stories and the critic (20 min): `stories.py`, graph edges in `workflow.py`

> **Why exactly one critic pass?** Without a bound, a critic and a writer can
> argue forever and spend the budget. `revision_count < 1` in the graph is the
> bound, not the prompt.

> **Why retry stories but not classification?** A bad classification has a safe
> fallback: hand it to a person as `unclear`. A story set with a duplicate has
> none. Accepting part of it would silently drop work, and a duplicate means two
> Jira tickets for one requirement.

### 6. The LLM helper and budget (30 min): `llm.py`, `run_store.py`

> **What if the provider doesn't return usage?** Cost becomes unknown and the
> helper refuses further calls in that run. The daily budget reserves the
> per-run maximum before a run starts and settles the real cost after.

### 7. Life of a run (40 min): `api.py` → `run_service.py` → `run_store.py` → `checkpoints.py` → `workflow.py`

Draw the path from `POST /runs` to the pause at review. A worker thread picks
queued runs from Postgres (at most 8 pending). Progress goes to the browser over
SSE. The LangGraph `thread_id` is the run ID.

> **What happens if the API restarts in the middle of `classify`?** The run is
> marked as an error, "start a new run". The model call may already have been
> paid for, and replaying it blindly isn't safe. Only a run paused at
> `human_review` resumes, because that node does nothing but wait.

> **When is the cache used?** Only for the fictional presets. The key hashes the
> transcript, the spec, both model names and the source of `stories.py`,
> `workflow.py` and `graph.py`, so changing the code invalidates it.

### 8. Jira (40 min): `jira/client.py`, `jira/ledger.py`, tests `test_jira.py`, `test_approval_race.py`

Draw Approve → ledger → Jira and walk through three crashes:

| Crash point | On retry |
|---|---|
| Before the ledger INSERT commits | Nothing recorded, nothing created: safe to retry |
| After INSERT, before Jira answers | Row with no result: blocked, "reconcile before retrying" |
| After Jira created the issue, before UPDATE | Same: blocked, because only a person (or a search by label) can confirm |

A 4xx from Jira means nothing was created, so the row is deleted and a fixed
retry can proceed. A 429 is retried up to three times with 1, 2 and 4 second
waits. A 5xx on create is never retried automatically.

> **Why not just retry the POST on timeout?** A timeout doesn't mean the ticket
> wasn't created, and Jira has no idempotency key on create. A duplicate costs
> more than asking a person to check.

### 9. Evals and CI (40 min): `evals/run_evals.py`, `evals/quality.py`, a case file, `.github/workflows/api.yml`

> **How are precision and recall computed?** Predicted and gold requirement
> texts are embedded. The most similar pair above the threshold is matched
> first, and each item matches once. Precision is matched/predicted, recall is
> matched/gold. The threshold (0.58) was calibrated for the local embedding
> model on hand-checked pairs and must be recalibrated for a different one.

> **Why aren't model evals run on every PR?** They cost money and are noisy.
> CI always tests the scoring code; real model runs are manual or opt-in.

> **Is the judge trustworthy?** No. It was measured on ten stories: MAE 0.5,
> but weighted kappa 0.19, and it missed invented scope. That result is the
> answer.

### 10. Frontend (20 min): `apps/web/app/page.tsx`, `story-editor.tsx`, `app/demo-api/[...path]/route.ts`

> **How does the public demo work without a backend?** With `DEMO_REPLAY=true`,
> `/api/*` is served by a route that replays recorded runs with their real
> timing. That means no model spend, no secrets and no Jira writes.

### 11. Tell it in five minutes

Draw the architecture from memory, then tell the story: the problem from
discovery work, the demo, three decisions (grounding, ledger, human approval),
the numbers, and what didn't work. Then do it again in English and in Polish.

If someone asks who wrote the code, the honest answer is: "I work AI-first.
Agents wrote code against my contracts and phases. The decisions, the spec, the
acceptance and the failure analysis are mine. Ask me about any module." That
answer only holds if you've walked this route.
