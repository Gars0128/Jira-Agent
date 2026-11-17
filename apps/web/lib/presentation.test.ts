import assert from "node:assert/strict";
import test from "node:test";
import { followUps, sectionTitle, costLabel, draftErrors, safeJiraUrl, safeTraceUrl } from "./presentation.ts";
import type { Story } from "./types.ts";

const story: Story = { id: "S1", title: "Export a report", as_a: "administrator", i_want: "an export", so_that: "I can review it", acceptance_criteria: ["Given a report, when I export, then a CSV downloads"], requirement_ids: ["R1"], idempotency_key: "server-owned" };

test("unknown billing is never presented as free", () => {
  assert.equal(costLabel(null), "—");
  assert.equal(costLabel("invalid"), "—");
  assert.equal(costLabel("0"), "$0.0000");
});

test("trace links accept only HTTPS LangSmith URLs without credentials", () => {
  assert.equal(safeTraceUrl("https://smith.langchain.com/o/demo/r/123"), "https://smith.langchain.com/o/demo/r/123");
  for (const unsafe of ["javascript:alert(1)", "data:text/html,attack", "https://smith.langchain.com.attacker.test", "https://secret@smith.langchain.com", "http://smith.langchain.com", "/relative", ""]) assert.equal(safeTraceUrl(unsafe), null);
});

test("edited stories need complete text and eligible links", () => {
  assert.deepEqual(draftErrors([story], ["R1"]), []);
  assert.equal(draftErrors([{ ...story, title: " ", acceptance_criteria: [""], requirement_ids: ["R2"] }], ["R1"]).length, 4);
  assert.ok(draftErrors([story, story], ["R1"]).some((error) => error.includes("Duplicate")));
});

test("approval preserves coverage and unique requirement links", () => {
  assert.ok(draftErrors([], ["R1"]).some((error) => error.includes("Every new requirement")));
  assert.ok(draftErrors([{ ...story, requirement_ids: ["R1", "R1"] }], ["R1"]).some((error) => error.includes("unique")));
});

test("Jira links accept only HTTPS Atlassian Cloud URLs without credentials", () => {
  assert.equal(safeJiraUrl("https://demo.atlassian.net/browse/KAN-2"), "https://demo.atlassian.net/browse/KAN-2");
  for (const unsafe of ["javascript:alert(1)", "https://atlassian.net.attacker.test/browse/X", "https://a:b@demo.atlassian.net/", "http://demo.atlassian.net/", ""]) assert.equal(safeJiraUrl(unsafe), null);
});

test("spec sections are shown by title, not by internal ID", () => {
  assert.equal(sectionTitle("## HD-EXPORT \u2014 Report export permissions and format\n\nOnly administrators..."), "Report export permissions and format");
  assert.equal(sectionTitle("Plain text without a heading"), null);
});

test("replay follow-up tasks match the API: decisions for conflicts, questions for unclear", () => {
  const base = { type: "functional", priority: "must", quote: "q", speaker: "Nora", spec_refs: [], note: null };
  const tasks = followUps([
    { ...base, id: "R1", text: "Show counts", status: "new" },
    { ...base, id: "R2", text: "Let coordinators  export", status: "conflict" },
    { ...base, id: "R3", text: "Make it fast", status: "unclear" },
    { ...base, id: "R4", text: "Keep CSV", status: "duplicate" },
  ]);
  assert.deepEqual(tasks.map(({ kind, summary }) => ({ kind, summary })), [
    { kind: "decision", summary: "Decide: Let coordinators export" },
    { kind: "question", summary: "Ask the client: Make it fast" },
  ]);
});
