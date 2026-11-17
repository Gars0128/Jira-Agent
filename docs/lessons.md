# Development lessons

Read before each task. Prefer executable regression checks to instructions. Keep
current status in [plan.md](plan.md), design reasons in [decisions.md](decisions.md),
and recurring failures here. Agents maintain this file deliberately; the installed
Harness skill provides guidance, not an automatic memory hook.

| Observed failure | Shared fix | Check | Remaining limit |
|---|---|---|---|
| Config import assumed a deep repository path | Settings reads environment; `uv --env-file` explicitly loads root settings | Configuration tests and Docker path review | Local container runtime remains deferred |
| Trace outage could discard a paid result | Bound URL/flush/close operations and preserve result with generic warnings | `tests/test_extraction.py` tracing failures | Trace delivery is unverified during an outage |
| Failed usage could appear free | Unknown cost blocks more calls and retains budget reservation | Shared helper usage tests and run-store budget checks | Provider billing remains authoritative |
| Classification request exceeded admission budget | Send each specification excerpt once and reference IDs | Classifier tests and phase-5 live run | Byte admission is an estimate |
| Valid JSON looked semantically correct | Separate schema validation, quote grounding and gold/model evaluation | Corpus evals and evidence review | Small corpus includes disputed labels |
| Deferred Docker looked completed | Preserve explicit deferred checks and resume conditions | Plan checkpoint and release checklist | Neon does not validate Docker |
| Eval stopped after paid cases without saving failed usage | Save every case, retain sanitized errors/usage, resume by recorded IDs, and reserve unknown cost | `tests/test_evaluation.py` failure accounting and resume checks | Legacy partial reports lack retrieval/latency data and lost-call billing |
| A live test's queued row was consumed by the local API worker | Give every live database test a separate temporary schema and connection search path | Live concurrency, run-store and RAG tests | Run tests only against the explicitly selected test connection |
| Integration tests inherited live Jira settings from a changed env file | Pin public dry-run and empty Jira credentials in test settings, block synchronous/asynchronous external HTTP, and require explicit API runtime injection | `tests/test_test_isolation.py` and live approval checks under the real env | Database access is separately scoped to temporary test schemas |
| A busy run at the front of the queue blocked other workers | Catch the specific busy condition per run and continue scanning | `tests/test_worker.py` | One synchronous worker per API instance is intentional for this demo |
| Browser polling could overwrite a newer state or human edits | Use one abortable snapshot reader and preserve edits during review | Browser concurrency and mode-change regression tests | Browser acceptance still requires a person |
| A successful subset or RAG baseline could look like a full quality pass | Validate scope, cohort, completeness and errors; preflight baseline before paid checks | Evaluation gate regression tests | Model/annotation quality still requires human calibration |
| A new Jira `url` field was silently dropped by the `TicketResult` response allowlist; mocked browser tests never crossed the real contract | Declare `url` on `TicketResult` | `test_run_response_keeps_live_ticket_link` | Every new client field still needs a contract update |
| A definite Jira failure (401/403 search, 4xx create) left the ledger intent NULL, blocking that story forever as "unconfirmed" | `JiraRejected` for failures where nothing was created; the ledger deletes its NULL intent on it, 5xx/transport stay ambiguous | `test_definite_jira_failures_are_rejections`, `test_live_rejected_jira_write_releases_ledger` | An ambiguous 5xx still needs manual reconciliation in Jira |
| Story fields repeated the words the UI and Jira add ("As a As a cooperative lead") with a local model | A `StoryDraft` validator drops leading "As a"/"A"/"I want"/"so that" for model output and human edits | `test_story_drops_template_words_the_renderers_add` | "As a administrator" still uses a fixed "As a" |
| One story-rule break (a new requirement in two stories, or a non-new ID) failed one case in each of three local baseline runs | `write_stories` retries once with the broken rule as revision feedback; a second break still fails | `test_story_rule_break_is_retried_once_with_the_error`, `test_story_rule_break_after_the_retry_fails` | Lost cases fell from one per run to one in three runs; a coverage gap can survive the retry |

For a new entry, name the observed defect and an actual check. Do not duplicate
the specification or add speculative rules.
