import type { Story } from "./types.ts";

export const steps = [
  { id: "extract", label: "Extract requirements", detail: "Verbatim client evidence" },
  { id: "retrieve_spec", label: "Search specification", detail: "Retrieve the relevant context" },
  { id: "classify", label: "Classify requirements", detail: "Find conflicts and duplicates" },
  { id: "write_stories", label: "Draft user stories", detail: "Testable acceptance criteria" },
  { id: "critic", label: "Review story quality", detail: "One bounded revision cycle" },
  { id: "human_review", label: "Your review", detail: "Edit, decide, and approve" },
  { id: "create_tickets", label: "Jira preview", detail: "Human-approved output" },
];

export const statusInfo = {
  new: { label: "New work", meaning: "Not in the spec yet — becomes a Jira story" },
  conflict: { label: "Conflicts with spec", meaning: "Contradicts an approved rule — needs a decision" },
  duplicate: { label: "Already in spec", meaning: "Already agreed — no new ticket needed" },
  unclear: { label: "Needs clarification", meaning: "Too vague to build — ask the client" },
} as const;

export function safeJiraUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password && url.hostname.endsWith(".atlassian.net") ? url.href : null;
  } catch {
    return null;
  }
}

export function costLabel(cost: string | number | null | undefined): string {
  if (cost === null || cost === undefined || !Number.isFinite(Number(cost))) return "—";
  return `$${Number(cost).toFixed(4)}`;
}

export function safeTraceUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password &&
      (url.hostname === "smith.langchain.com" || url.hostname.endsWith(".smith.langchain.com")) ? url.href : null;
  } catch {
    return null;
  }
}

export function draftErrors(stories: Story[], allowedIds: string[]): string[] {
  const errors: string[] = [];
  const seen = new Set<string>();
  const covered = new Set<string>();
  for (const story of stories) {
    if (seen.has(story.id)) errors.push(`Duplicate story ID: ${story.id}`);
    seen.add(story.id);
    if ([story.title, story.as_a, story.i_want, story.so_that].some((value) => !value.trim())) errors.push(`${story.id}: complete all story fields.`);
    if (!story.acceptance_criteria.length || story.acceptance_criteria.some((value) => !value.trim())) errors.push(`${story.id}: add a nonempty acceptance criterion.`);
    if (!story.requirement_ids.length || story.requirement_ids.some((id) => !allowedIds.includes(id))) errors.push(`${story.id}: link only eligible requirements.`);
    if (new Set(story.requirement_ids).size !== story.requirement_ids.length) errors.push(`${story.id}: requirement links must be unique.`);
    for (const id of story.requirement_ids) covered.add(id);
  }
  if (allowedIds.some((id) => !covered.has(id))) errors.push("Every new requirement needs a story before approval.");
  return errors;
}
