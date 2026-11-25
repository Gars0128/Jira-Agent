---
name: verify-tiro
description: Drive Tiro's web UI (Next.js, recorded-replay mode) the way a user does and capture evidence - pick a call, run discovery, review tickets and their evidence, edit a story, approve a Jira preview, plus WCAG/focus/reduced-motion checks. Use before saying a UI, copy, replay-data or board change is done, or whenever "verified in the running app" is required.
---

# Verify Tiro in the running app

Tiro turns a client-call transcript into Jira tickets a person approves. The user touches one surface: the web page in `apps/web`. This skill drives it in **replay mode** (`DEMO_REPLAY=true`): the Next.js route `apps/web/app/demo-api/[...path]/route.ts` answers `/api/*` with seven real recorded runs from `apps/web/demo/runs.json`. No database, API key, model call or Jira write is involved, and every run is reproducible.

The FastAPI backend (`apps/api`) is a second surface that this skill does not launch: it needs `.env`, Postgres with pgvector and a paid or local (Ollama) model. Backend behavior is covered by `uv run pytest` in `apps/api`; a live end-to-end run costs money and needs the user's go-ahead (see `start.ps1` and README "Run it locally").

All commands run from the repo root. One helper does everything:

```
node .claude/skills/verify-tiro/scripts/tiro.mjs start [--port 3107]
node .claude/skills/verify-tiro/scripts/tiro.mjs doctor
node .claude/skills/verify-tiro/scripts/tiro.mjs journey <analyze-call|review-evidence|approve-preview|accessibility|all>
node .claude/skills/verify-tiro/scripts/tiro.mjs stop
```

Prerequisites: Node 24, `npm ci` done in `apps/web`, Playwright's Chromium installed (`npx playwright install chromium` in `apps/web` if a journey says the browser is missing).

## Launch

`tiro.mjs start` runs `npx --no-install next dev -p 3107` in `apps/web` with `DEMO_REPLAY=true`, writes `.verify/server.json` (pid, port, url, commit) and the log to `.verify/server.log`, and returns when `GET /api/capabilities` reports `"replay": true` (usually 2-5 s). Ready means usable: `doctor` additionally waits until the page hydrates and **Run discovery** is enabled; trust that, not the HTTP answer alone.

- It refuses to start if its own instance is alive or if the port already answers. Pick another port with `--port`; never drive an instance this skill did not start.
- The URL is `http://localhost:<port>`, not `127.0.0.1`: Next dev blocks its client scripts for that origin, the page never hydrates and every button stays disabled.

## Doctor

`tiro.mjs doctor` is read-only and answers "is this instance worth driving?": `server.json` exists, the pid is alive, capabilities say replay and Jira dry-run, `HEAD` is the commit the server started at, and the page hydrates. Run it first and whenever a journey fails strangely. A commit mismatch means you are testing new code on a dev server that hot-reloaded; that is fine for UI edits, but restart (`stop`, `start`) after changing `next.config.ts`, env or dependencies.

## Drive

`tiro.mjs journey <name>` opens Chromium at 1440x900, performs the feature's user path and prints PASS/FAIL per check; exit code 1 if any check fails. The recipes and the selectors they rely on are in [features/](features/README.md). Use the journey when one exists; for anything not covered, write a throwaway Playwright script with the same handles:

- Buttons by accessible name: `Run discovery`, `Analyzing conversation`, `Create N tickets (preview)` (inside `.approval-bar`), `Save`, `Close`.
- Board columns are regions named `To build`, `Needs decision`, `Ask the client`; each card is a button inside its region.
- `#results-heading` is the results title (`N tickets from this call`, `Done`); `#transcript` is the transcript; selects are comboboxes named `Project` and `Conversation` (use `exact: true`).
- The ticket dialog is the page's `dialog`; its title is `#dialog-title`; story fields use labels such as `Title`.
- Wait for state by text, not time: `Your review is ready` (pipeline panel) and the `Done` heading.

## Evidence

Each journey writes `.verify/evidence/<timestamp>-<journey>/`:

- numbered screenshots of the action and of the resulting state (`1-before-run.png`, `2-running.png`, `3-review.png`, ...);
- an ARIA snapshot (`*.aria.yml`) of the key state;
- `result.json`: every check with pass/fail, the URL, the commit, and the origins of every request the page made;
- `axe-review.json` for the accessibility journey; `failure.png` when a journey throws.

Proof standards for this app:

- Drive the real user path. Never call `/api/...` or set React state to fake a step.
- "Preview / nothing sent" is a claim, so prove the side effect: `approve-preview` fails if any request leaves `localhost`.
- An edit is proven only when a second view shows it: the edited story title must appear on the card and on the `Done` board after approval.
- Put the evidence folder path and the PASS/FAIL lines in your reply. If a journey could not run, say "inconclusive" and why.

## Cleanup

`tiro.mjs stop` kills only the pid tree recorded in `.verify/server.json` (`taskkill /T` on Windows, the process group elsewhere) and deletes that file. It never kills by process name and never touches `.verify/evidence/`. Run `stop` after every session, including after a failed run. Evidence folders are git-ignored; delete old ones by hand when you no longer need them.

## Gotchas

- Replay timing is real: review appears about 9.4 s after **Run discovery**, approval takes about 1.8 s. Journeys wait on text with a 30 s timeout.
- The replay rejects any transcript that is not a recorded sample, so the transcript is read-only there. Do not test "paste your own text" in replay; it needs the real backend.
- Changing `apps/web/demo/runs.json` by hand breaks the replay's load-time checks (`oneOf` in the route) and the API test `test_recorded_demo_follow_ups_match_the_rule`; run `uv run pytest` in `apps/api` after touching it.
- The Next dev-tools button (round "N", bottom left) exists only in dev mode; ignore it in screenshots.
