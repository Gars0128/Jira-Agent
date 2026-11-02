# Instructions for Codex and Claude Code

Read this file in full before each task, then the [plan](docs/plan.md) and relevant sections of the [specification](docs/spec.md). README is the human entry point; this file contains shared agent instructions.

## Working together

- Keep repository documentation, API names, classes, and fields in English. Discuss the work and report to the user in Russian.
- Work only on the agreed phase or explicitly authorized batch. A request to start a phase authorizes its implementation and necessary checks.
- Before editing, briefly explain the goal, scope, and verification. Read the affected files and their callers.
- Make the smallest complete change. Do not add dependencies, abstractions, or features for hypothetical future use.
- Run appropriate checks after implementation. Fix failures and rerun affected checks; report environment limitations explicitly.
- Finish with changed files, actual commands and results, manual verification steps, and remaining limitations.
- Stop after reporting. Begin the next phase only after the user's confirmation.
- Explain decisions in plain language so the user can learn and verify the result.
- Within a phase, use small steps: explanation → implementation → checks → user practice → discussion. Wait for confirmation before the next step; do not deliver a large phase as an opaque batch.
- Introduce concepts through current code: inputs, processing, outputs, and where to observe the result. Explain LangGraph state, nodes, edges, interrupts, and checkpoints as they appear. Do not assume prior LangChain or LangGraph knowledge.
- Do not mark a phase accepted before manual confirmation. Never present planned features, metrics, or deployment as completed work.

## Current checkpoint

- **Docker step 2.2 is deferred by the user's decision, not completed.** Do not enable the hypervisor, change Windows boot settings, reboot, or retry Docker unless requested. The reason, outstanding checks, and resumption criteria are recorded in the [plan](docs/plan.md).
- The user authorized two parallel work streams for the current batch only: step 2.3 (CI) and phase 3 (demo data), alongside the English documentation update. This does not authorize subsequent phases or permanent autonomous operation. Keep manual acceptance pending.
- Revisit the deferred database setup before work that needs a live database. Do not silently replace local Postgres with a cloud service.

## Engineering constraints

- All demo data is fictional. Never use real client names, conversations, or documents.
- Read secrets and configuration from the environment. Never commit `.env` or print secrets in logs.
- Python: type hints, `ruff`, and `pytest`. TypeScript: strict mode and ESLint. Add concrete commands with the corresponding implementation and configuration.
- Non-trivial logic needs a small behavioral check. For documentation changes, check links, consistency, and the diff.
- Route every LLM call through one helper that records tokens and cost and enforces `MAX_COST_PER_RUN_USD`.
- Check grounding in code: discard empty quotes and quotes absent from the transcript after whitespace/case normalization. Preserve the original quote text.
- Write to Jira only from `create_tickets`, after `human_review` and an Approve request. Default `JIRA_DRY_RUN=true`; the public demo always uses dry-run.
- Check idempotency before Jira creation; retry 429/5xx with exponential backoff, at most three retries. See the specification for the contract.
- Run evals before merging prompt or model changes. Until an eval runner exists, state that model quality has not been measured.
- Record non-obvious choices in [docs/decisions.md](docs/decisions.md).

## Using skills

- **Ponytail:** the smallest complete implementation within the agreed scope.
- **Matt Pocock:** choose the specific skill needed for requirements, TDD, diagnosis, teaching, or review. Do not run the whole collection automatically.
- **Thermonuclear Review:** a separate strict maintainability review, only on an explicit user request.
- **Agent Harness Construction:** use when designing our agent's tools, output formats, and recovery behavior. Keep project checkpoints in the plan rather than introducing another memory system.
- **pstack:** installed in Claude Code; use compatible workflows when useful. Do not assume full Codex support.
- An installed skill is not necessarily an applied skill. Do not enable autonomous execution or parallel agents merely because a plugin exists. User instructions and phase boundaries take priority.

Skills are installed per user and may be absent on another computer. The project's essential rules are recorded here and do not require plugins.
