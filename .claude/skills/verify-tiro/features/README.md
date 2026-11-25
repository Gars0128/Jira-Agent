# Tiro verification map

The maintained source for verifying what a user can do in Tiro's web UI. Read this index, then use the matching feature file as the recipe. Each feature has a journey in `scripts/tiro.mjs` with the same name.

| Feature | Journey | What it proves |
|---|---|---|
| [Analyze a call](analyze-call.md) | `analyze-call` | A recorded call runs to a review board with tickets in all three columns |
| [Review and evidence](review-evidence.md) | `review-evidence` | Every ticket explains itself; a story edit sticks |
| [Approve a Jira preview](approve-preview.md) | `approve-preview` | Approval keeps edits, marks every ticket Preview, sends nothing off the machine |
| [Accessibility](accessibility.md) | `accessibility` | WCAG 2.2 AA, focus management, mobile layout, reduced motion |

## Baseline preconditions

- `tiro.mjs start` launched the instance and `tiro.mjs doctor` prints only `ok` lines.
- Replay mode: `GET /api/capabilities` returns `"replay": true` and `"jira_dry_run": true`.
- Default selection is project `Harbor Desk (with specification)`, conversation `01 Exports`. Its recorded run yields 4 requests: 1 already in the spec, 1 story, 1 decision, 1 client question.
- Never drive an instance this skill did not start.

## Driving conventions

- Every journey starts from a fresh page load; replay keeps no server state between runs, so no data reset is needed.
- Prefer accessible roles and names; CSS selectors are used only for `#results-heading`, `#transcript`, `.approval-bar`, `.jira-meta` and `.page-heading .problem`, which have no better handle.
- Wait on visible text (`Your review is ready`, `Done`), never on fixed sleeps longer than an animation.

## Proof and skip reporting

- Capture the action and the resulting state, not only the final screen; journeys number their screenshots in order.
- Report the evidence folder and the PASS/FAIL lines. A FAIL is a finding: report it, do not loosen the check to make it pass.
- Report an entry point you could not reach (for example the real backend) as not verified, with the reason; do not count a replay run as proof of backend behavior.

## Feature entry contract

Each feature file has an H1, one paragraph on the user-visible behavior, then exactly these H2s in order: `Sub-features`, `How to get to it (user POV)`, `Driving it with tiro.mjs`, `Gotchas`.
