# Analyze a call

A user picks a recorded client call, presses Run discovery, watches the agent's steps tick off, and lands on a review board that sorts the call's requests into tickets to build, decisions and questions for the client.

## Sub-features

- `hero-problem` the first screen states the problem before the product.
- `pick-call` choose a project and one of the recorded conversations.
- `replay-readonly` in the hosted replay the transcript is read-only and "Write your own" is absent.
- `run` Run discovery starts the run; the button reads "Analyzing conversation" while it works.
- `progress` the pipeline panel marks steps done and shows LIVE.
- `review` the results heading counts tickets and the board has three columns.

## How to get to it (user POV)

- Open the site; the Run discovery button is on the first screen with the default call selected.
- Change the `Conversation` select to another call, then press Run discovery.
- Reopen a URL with `?run=<id>`; the page resumes that run (replay ids look like `replay~harbor-desk:01-exports~<ms>`).

## Driving it with tiro.mjs

Preconditions:

- Baseline from the index; `doctor` clean.

- **First screen.** Load the page. Run `node .claude/skills/verify-tiro/scripts/tiro.mjs journey analyze-call`. Checks `.page-heading .problem` is visible and the Run discovery button's bottom edge is inside the 1440x900 viewport.
- **Pick call.** The journey selects `01 Exports` in the combobox named `Conversation` and screenshots `1-before-run.png`.
- **Run.** It clicks `Run discovery`, waits for the button `Analyzing conversation`, screenshots `2-running.png`, and checks focus moved to `#results-heading`.
- **Review.** It waits for the text `Your review is ready`, checks the heading matches `N tickets from this call`, and that regions `To build`, `Needs decision`, `Ask the client` each hold a card button. Proof: `3-review.png` and `review.aria.yml`.

## Gotchas

- Use `getByRole("combobox", { name: "Conversation", exact: true })`; `getByLabel("Conversation")` also matches the "Start with a conversation" panel.
- A run restored from `?run=` does not scroll when the page opens; it still scrolls and moves focus to `#results-heading` once its review is ready.
- The grooming-salon project has no spec, so its board has no Needs decision column; the journey's three-column check is for Harbor Desk.
