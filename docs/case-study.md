# Tiro: implementation and measured limits

This educational MVP turns a fictional discovery-call transcript into grounded
requirements, specification comparisons, reviewed stories, and Jira previews.
The approved scope is in [spec.md](spec.md); current verification is in
[plan.md](plan.md). Source code and configuration are not proof of a deployment.

## Data flow

The shared LLM helper accounts for model and embedding calls and blocks calls
that cannot fit the estimated per-run budget. LangChain requests structured
outputs; Pydantic validates them. Code filters quotes against the transcript.
LangGraph connects extraction, pgvector retrieval, classification, story writing,
a single critic pass with at most one revision, and human review. Approval is the only path to ticket
creation. The public demo must force dry-run, regardless of client input.

## Existing measurements

On 2026-11-02, the phase-5 v2 run used 29 gold requirements across 12 cases,
bypassing extraction. Retrieval recall@5 was 28/29 (0.966), status accuracy
26/29 (0.897), and conflict F1 10/13 (0.769; TP 5, FP 3, FN 0). Estimated model
and embedding cost was approximately $0.068. These are single-run measurements,
not averaged confidence estimates or end-to-end quality results.

One earlier transcript smoke run took 7.8 seconds and approximately $0.0131.
It did not exercise story generation, approval, or the complete browser journey.
The less-than-two-minute final product target has not been established by it.

Three classifications remained disputed. Saved presets were labeled new in gold
but treated as conflicting with the baseline by the model in two cases. One
public-status-page requirement retrieved access-control context instead of the
operations section. Prompt tuning stopped rather than repeatedly fitting the
same small corpus. A reviewer must resolve annotation ambiguity before replacing
the reference labels.

### Full-workflow sample: quality gate not met

This run predates the critic-once and jokes/deferred-idea extraction prompt changes; quality with the current prompts is unmeasured.

The saved [full report](../evals/full-report.json) contains 12 attempted cases,
29 gold requirements and 32 returned requirements. Under the specified one-to-one
cosine threshold of 0.8, 11 matched: precision **0.344**, recall **0.379**.
End-to-end conflict F1 was **0.286** (TP 2, FP 7, FN 3); status accuracy among
matched requirements was **9/11 (0.818)**. These F1 counts include unmatched
predictions and missed gold conflicts; they are not classification-only quality.
Returned quotes were grounded **32/32**. Judge mean was **3.857/5 on 7 stories**,
without the required human calibration. Case `05-usability` failed because the
model cited an excerpt not retrieved for that requirement; the pipeline correctly
rejected it rather than inventing evidence. That failed case contributes missed
requirements to recall and prevents acceptance independently of aggregate scores.

Known evaluation cost was **$0.18068246**, plus a conservative **$0.30 reservation**
for a legacy interrupted call whose usage was not saved. This reservation is not
a claim of actual billing. The resumed legacy samples lack retrieval and timing
data: reported retrieval **1.0 on only 4 matched requirements** is conditional and
cannot replace the phase-5 29-requirement measurement. Workflow p95 was about
**27.7 seconds on 8 timed cases**, excluding three legacy samples and the failed
case; it is not complete end-to-end browser p95.

Offline review found that the matcher's slicing, cosine formula and one-to-one
matching follow the agreed rule. Several unmatched pairs are close paraphrases,
including “Restrict report export to administrators” versus “Only administrators
may export reservation reports.” No embedding vectors or cosine scores were saved
for that run, so the exact numerical cause cannot be independently recomputed.
Future samples save their cosine matrices using the embeddings already requested,
without additional model calls. The threshold remains **0.8**.

The reference annotations also omit explicitly discussed behavior: audit-token
logging in case 02, rejecting revoked invitations and keeping 72-hour expiry in
case 03, and subscription expiry/email-only constraints in case 04. Some model
outputs split one gold requirement into several items. This reveals annotation
scope/granularity questions, not permission to relabel gold to fit the model.
There are also actual classification errors, such as treating a new monthly count
or a service-only status page as a policy conflict. Human annotation review and
matching calibration must separate these causes before a controlled rerun.
The failed report is retained as evidence; **no full baseline was frozen from it**.

LangSmith dataset **`discovery-jira-gold-v1` was uploaded with 12 fictional cases**.
The [judge worksheet](../evals/calibration-review.json) contains the seven actual
judge-rated stories and three pending rows, with all human ratings left empty.
The active [calibration file](../evals/calibration.json) remains unapproved.

## Evaluation commands

From `apps/api`, after configuring the ignored root `.env`:

```powershell
python -m uv run --env-file ../../.env python ../../evals/run_evals.py --check
python -m uv run --env-file ../../.env python ../../evals/run_evals.py --mode full --judge --output ../../evals/full-report.json
python -m uv run --env-file ../../.env python ../../evals/sync_dataset.py
```

These commands make paid calls or upload the fictional corpus. The first
isolates retrieval/classification using gold requirements. Full mode executes
through the human-review interrupt without approving or creating tickets.
It matches predicted and gold requirements one-to-one at cosine similarity
at least 0.8, reports precision/recall, quote grounding, conflict F1, story judge
ratings, total evaluation cost, and nearest-rank p95 workflow latency with sample
counts. Each sample separates workflow usage from added matching/judge usage.
The evaluation process admits another case only if its remaining daily allowance
can cover the configured per-run maximum. `--output` preserves completed samples
as a partial report if a subsequent case fails. This process allowance is separate
from the API's persisted daily reservation ledger; account for other paid work
when scheduling evals.

After interruption, continue with `--resume-from path/to/report.json --output
path/to/report.json` using the same mode and judge option. Recorded case IDs,
including failures, are skipped. New failures preserve usage and a sanitized stage
reason and do not discard successful cases; any failed case returns exit status 2.
Use `--case 04-bookings` with a separate output only for a deliberate rerun after
diagnosis. Legacy partial reports lacked failed-call usage and retrieval/latency
measurements: resumption reserves one per-run maximum for the lost cost and
reports retrieval/latency only for samples that actually saved those measurements.

`evals/baseline.json` is fixed and never rewritten by a runner. Its end-to-end
precision/recall fields remain null until a real report is reviewed and committed.
Full `--check` intentionally fails with missing baselines or missing judge
calibration. The judge requires ten distinct actual examples rated by a person;
enter human and judge scores in `evals/calibration.json`, review the reported
mean absolute error, and set `approved` only after accepting agreement. No human
ratings are fabricated. Story mean must be at least 3.5/5 and grounding 1.0 on
nonempty output; precision, recall and conflict F1 must remain within 0.05 of
the reviewed baseline. Small-talk cases contribute to false-positive checks.

CI always tests the scoring/gating implementation, including a deliberately bad
result that returns exit status 1. Actual model evaluation runs on manual workflow
dispatch, or same-repository PRs when `ENABLE_MODEL_EVALS=true` is configured as
a repository variable. Configure secrets `OPENAI_API_KEY`, `EVAL_DATABASE_URL`
and variables `LLM_MODEL`, `LLM_INPUT_USD_PER_MILLION`,
`LLM_OUTPUT_USD_PER_MILLION` first. Use a dedicated evaluation database. Forked
PRs do not receive credentials. Offline tests do not measure a live model.
The configured model CI job is explicitly RAG-only, not an end-to-end production
quality guarantee. A full `--check` requires a separately reviewed full-scope
baseline and manual judge calibration. Incomplete/error cases and mismatched
baseline cohorts cannot pass, and missing baseline setup is rejected before any
paid evaluation call.

## Release boundary

`render.yaml` describes a Docker API with `/health` and public dry-run settings.
Configure its private environment values in Render; configure the web's
server-side `API_URL` to the deployed API URL in Vercel. Never expose OpenAI,
database or Jira keys as `NEXT_PUBLIC_*`. Deployment must also verify migrations,
specification ingestion, checkpoint restart recovery, daily budget enforcement,
public dry-run, and the entire browser workflow. A health response establishes
liveness, not those acceptance checks.

Docker on the development machine remains deferred because the Windows
hypervisor is off. No public URL, GIF, ten human judge scores, production timing,
or successful hosting deployment is claimed in this document.
