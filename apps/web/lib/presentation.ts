import type { Requirement, Story, TicketKind } from "./types.ts";

export const steps = [
  { id: "extract", label: "Find the requests", detail: "Each one keeps the client's exact words" },
  { id: "retrieve_spec", label: "Check the project spec", detail: "Looks up the rules already agreed" },
  { id: "classify", label: "Sort each request", detail: "New, already agreed, conflicting or unclear" },
  { id: "write_stories", label: "Draft tickets", detail: "With testable acceptance criteria" },
  { id: "critic", label: "Double-check the tickets", detail: "One automatic review pass" },
  { id: "human_review", label: "Your review", detail: "Edit anything, then approve" },
  { id: "create_tickets", label: "Jira preview", detail: "What Jira will receive" },
];

export const ticketColumns: [TicketKind, string, string][] = [
  ["story", "To build", "New work for the team, with acceptance criteria."],
  ["decision", "Needs decision", "The client asked for something the spec rules out."],
  ["question", "Ask the client", "Too vague to build until the client answers."],
];

// shortcut: mirrors follow_ups() in apps/api/app/stories.py for the replay demo; the live API builds its own.
export function followUps(requirements: Requirement[]): { kind: TicketKind; summary: string; requirement: Requirement }[] {
  return requirements.filter((item) => item.status === "conflict" || item.status === "unclear").map((item) => {
    const kind = item.status === "conflict" ? "decision" : "question";
    return { kind, summary: `${kind === "decision" ? "Decide" : "Ask the client"}: ${item.text}`.split(/\s+/).join(" ").slice(0, 255), requirement: item };
  });
}


// Spec chunks start with "## HD-EXPORT — Report export permissions"; people need the title, not the ID.
export function sectionTitle(text: string): string | null {
  const heading = /^#+\s*(?:[A-Z][A-Z0-9-]*\s+[—-]\s+)?(.+)/.exec(text.split("\n", 1)[0]);
  return heading ? heading[1].trim() : null;
}

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
