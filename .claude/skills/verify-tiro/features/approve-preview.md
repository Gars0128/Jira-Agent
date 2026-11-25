# Approve a Jira preview

After review the user presses Create N tickets (preview). Tiro shows exactly what Jira would receive, keeps the user's edits, marks every ticket Preview, and sends nothing anywhere. This is the safety promise of the public demo.

## Sub-features

- `approve-bar` the approval bar stays in view (sticky) during review and names the ticket count and preview mode.
- `approve` the button reads "Creating…" and the board header "Sending…", then the heading becomes `Done`.
- `preview-only` every card shows `Preview` with a check mark; the summary says "Nothing was sent."
- `edits-kept` story edits made in review appear on the `Done` board.
- `no-egress` no request leaves the local origin.

## How to get to it (user POV)

- Finish a review, then press the button in the dark approval bar.

## Driving it with tiro.mjs

Preconditions:

- Baseline from the index; the journey runs `review-evidence` first so an edit exists.

- **Approve.** Run `node .claude/skills/verify-tiro/scripts/tiro.mjs journey approve-preview`. It checks the `.approval-bar` button text contains `(preview)` and the button is inside the viewport, then clicks it and waits for the heading `Done`.
- **State.** It checks `#results` contains `Nothing was sent.` and the edited title, and every `.jira-meta` reads `Preview`; focus is on the `Done` heading. Proof: `1-done.png`, `done.aria.yml`.
- **Side effect.** It fails if any request the page made went to an origin other than `http://localhost:<port>`; `result.json` lists the origins seen.

## Gotchas

- In replay, approval tickets are built by the route from `runs.json` `follow_ups`; a real Jira run needs the backend, `JIRA_DRY_RUN=false`, `PUBLIC_DEMO=false` and the user's explicit authorization. Never attempt it from this skill.
- The ticket keys in replay are synthetic (`PREVIEW-…`, `PREVIEW-T1`); do not assert on them.
