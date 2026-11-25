export type Project = {
  id: string;
  name: string;
  spec: boolean;
  transcripts: { id: string; name: string; text: string }[];
};

export type Requirement = {
  id: string; text: string; type: string; priority: string; quote: string; speaker: string;
  status: "new" | "duplicate" | "conflict" | "unclear" | null;
  spec_refs: string[]; note: string | null;
};

export type Story = {
  id: string; title: string; as_a: string; i_want: string; so_that: string;
  acceptance_criteria: string[]; requirement_ids: string[]; idempotency_key: string;
};

export type TicketKind = "story" | "decision" | "question";

// Built by the API from conflict and unclear requirements (follow_ups in apps/api/app/stories.py).
export type FollowUp = { kind: Exclude<TicketKind, "story">; title: string; requirement_ids: string[]; idempotency_key: string };

export type Ticket = { key?: string; url?: string; dry_run?: boolean; reused?: boolean; story_id?: string; kind?: TicketKind; summary?: string; fields?: { summary?: string }; [key: string]: unknown };

export type Run = {
  run_id: string;
  status: "queued" | "running" | "awaiting_review" | "done" | "error";
  requirements: Requirement[]; stories: Story[]; follow_ups: FollowUp[]; questions: string[];
  retrieved: Record<string, { id: string; text: string; distance: number }[]>;
  usage: { cost_usd: string | number | null; input_tokens?: number; output_tokens?: number; calls?: number };
  latency_ms: number; trace_url: string | null; tickets: Ticket[]; error: string | null; cached?: boolean;
};

export type RunEvent = { type: string; node?: string };

export type Capabilities = { public_demo: boolean; jira_dry_run: boolean; transcript_limit: number; replay?: boolean; model?: string };
