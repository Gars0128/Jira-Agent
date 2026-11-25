# Development lessons

Read before each task. A lesson lives here only when it needs judgment; everything
a type, lint rule, hook or test can hold lives there instead (see the trust pyramid
in [AGENTS.md](../AGENTS.md)). Keep current status in [plan.md](plan.md) and design
reasons in [decisions.md](decisions.md).

| Observed failure | Shared fix | Check | Remaining limit |
|---|---|---|---|
| Valid JSON looked semantically correct | Separate schema validation, quote grounding and gold/model evaluation | Corpus evals and evidence review | Small corpus includes disputed labels |
| Deferred Docker looked completed | Preserve explicit deferred checks and resume conditions | Plan checkpoint and release checklist | Neon does not validate Docker |

Fourteen earlier lessons were removed on 2026-11-25 because a mechanism now
catches a repeat: grounding, budget, tracing, eval resume and cohort gates,
test isolation, worker fairness, polling drafts, the Jira ledger and response
contract, story template words and the story retry each have a named test, and
the configuration path is a typed `Settings`. Their history is in git.

For a new entry, first try a type, a lint rule with a "do this instead" message,
a shared helper or a test. Add a row only if none can hold it, with an example of
the failure and never a secret.
