# Review and evidence

On the review board every ticket opens a dialog that shows why it exists: the client's exact quote and speaker, the agent's reason, and the spec section it relies on. Story tickets open an editor; an edit is saved back to the card.

## Sub-features

- `decision-evidence` a Needs decision card shows quote, speaker, "Why" and "From the spec".
- `question-evidence` an Ask the client card shows the same shape.
- `dialog-close` Escape or Close closes the dialog and returns focus to the card.
- `story-edit` a To build card opens the story editor; Save updates the card title.
- `long-titles` long summaries are clamped to two lines on the card; `#dialog-title` shows the full text.
- `skipped` "N request was already in the spec, so no ticket" expands to the skipped request and its quote.

## How to get to it (user POV)

- Click any card on the review board.
- Expand the "already in the spec" disclosure above the board.

## Driving it with tiro.mjs

Preconditions:

- Baseline from the index; the journey reaches the review itself.

- **Open a decision.** Run `node .claude/skills/verify-tiro/scripts/tiro.mjs journey review-evidence`. It clicks the first button in region `Needs decision` and reads the `dialog`: a curly-quoted quote, an em dash before the speaker, `Why`, `From the spec:`. Proof: `1-decision-dialog.png`.
- **Close.** It presses Escape and checks the dialog is hidden.
- **Edit a story.** It clicks the first card in `To build`, fills the field labelled `Title` with `Show monthly reservation counts in the report`, presses `Save`, and checks the card now shows that title. Proof: `2-story-edited.png`.

## Gotchas

- Only stories are editable; decision and question dialogs show a `Close` button, stories in review show `Save`.
- After approval the editor is read-only; edit before approving.
- The clamp is visual: the full title is still in the DOM, so assert on `#dialog-title` for the full text, not on the card's visible lines.
