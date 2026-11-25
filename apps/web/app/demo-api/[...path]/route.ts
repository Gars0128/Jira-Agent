// Recorded-run replay for the hosted demo (DEMO_REPLAY=true). It mimics the API
// contract with seven real stored runs, so the site works without a backend,
// model calls or Jira writes. Locally, /api goes to the real FastAPI service.
import recording from "../../../demo/runs.json";
import type { Run, Story } from "../../../lib/types";

type Recorded = Omit<Run, "run_id" | "status" | "tickets" | "error" | "trace_url">;
const runs = recording.runs as unknown as Record<string, Recorded>;

// Seconds after creation at which each node finishes, in order; review follows the last.
const finishedAt = { extract: 2.4, retrieve_spec: 3.4, classify: 5.2, write_stories: 7.6, critic: 9 } as const;
const reviewAt = 9.4;

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

// Returns the recorded run itself, so callers never look it up a second time.
function parseRun(id: string): { run: Recorded; started: number } | null {
  // Run IDs avoid "/" because the UI puts them in URL paths unencoded on approve.
  const groups = /^replay~(?<project>[\w-]+):(?<preset>[\w-]+)~(?<started>\d+)$/.exec(id)?.groups;
  const run = groups && runs[`${groups.project}/${groups.preset}`];
  return run && groups.started ? { run, started: Number(groups.started) } : null;
}

function snapshot(id: string, run: Recorded, started: number): Run {
  const elapsed = (Date.now() - started) / 1000;
  const done = (node: keyof typeof finishedAt) => elapsed >= finishedAt[node];
  const base = { run_id: id, trace_url: null, tickets: [], error: null, usage: run.usage, latency_ms: run.latency_ms, questions: run.questions };
  if (elapsed >= reviewAt) return { ...base, ...run, run_id: id, status: "awaiting_review", trace_url: null, tickets: [], error: null };
  return {
    ...base,
    status: "running",
    requirements: done("extract") ? run.requirements.map((item) => (done("classify") ? item : { ...item, status: null, spec_refs: [], note: null })) : [],
    retrieved: done("retrieve_spec") ? run.retrieved : {},
    stories: done("write_stories") ? run.stories : [],
    follow_ups: done("classify") ? run.follow_ups : [],
    questions: done("classify") ? run.questions : [],
    usage: { calls: 0, input_tokens: 0, output_tokens: 0, cost_usd: null },
    latency_ms: 0,
  };
}

function events(started: number): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: object) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      let previous = 0;
      for (const [node, finish] of Object.entries(finishedAt)) {
        const wait = started + previous * 1000 - Date.now();
        if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
        send({ type: "node_started", node });
        const remaining = started + finish * 1000 - Date.now();
        if (remaining > 0) await new Promise((resolve) => setTimeout(resolve, remaining));
        send({ type: "node_finished", node });
        previous = finish;
      }
      const review = started + reviewAt * 1000 - Date.now();
      if (review > 0) await new Promise((resolve) => setTimeout(resolve, review));
      send({ type: "awaiting_review" });
      controller.close();
    },
  });
  return new Response(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-store" } });
}

export async function GET(_request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path;
  // The recorded runs were made with this model; their usage below is real.
  if (path.join("/") === "capabilities") return json({ public_demo: true, jira_dry_run: true, transcript_limit: 20000, replay: true, model: "gpt-5.6-terra" });
  if (path.join("/") === "projects") return json({ projects: recording.projects });
  if (path.join("/") === "health" || path.join("/") === "ready") return json({ status: "ok" });
  const [resource, id, action] = path;
  if (resource === "runs" && id) {
    const replay = parseRun(id);
    if (!replay) return json({ detail: "Unknown run" }, 404);
    if (action === "events") return events(replay.started);
    if (path.length === 2) return json(snapshot(id, replay.run, replay.started));
  }
  return json({ detail: "Not found" }, 404);
}

export async function POST(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path;
  const body = await request.json().catch(() => null);
  if (path.length === 1 && path[0] === "runs") {
    const key = `${body?.project_id}/${body?.preset_id}`;
    const preset = recording.projects.find((item) => item.id === body?.project_id)?.transcripts.find((item) => item.id === body?.preset_id);
    if (!(key in runs) || preset?.text !== body?.transcript) {
      return json({ detail: "This hosted demo replays recorded runs. Pick a sample conversation, or run Tiro locally to analyze your own text." }, 422);
    }
    return json({ run_id: `replay~${body.project_id}:${body.preset_id}~${Date.now()}` }, 202);
  }
  const [resource, id, action] = path;
  if (resource === "runs" && id && action === "approve") {
    const replay = parseRun(id);
    if (!replay) return json({ detail: "Unknown run" }, 404);
    const stories = (Array.isArray(body?.stories) ? body.stories : []).slice(0, 30) as Story[];
    // A short pause lets the board show "Creating…" as it would with Jira.
    await new Promise((resolve) => setTimeout(resolve, 1800));
    const tasks = replay.run.follow_ups.map(({ kind, title }, index) => ({ key: `PREVIEW-T${index + 1}`, dry_run: true, reused: false, kind, summary: title }));
    const tickets = [...stories.map((story) => ({ key: `PREVIEW-${String(story.idempotency_key).slice(0, 8)}`, dry_run: true, reused: false, kind: "story", summary: String(story.title), fields: { summary: String(story.title) } })), ...tasks];
    return json({ ...snapshot(id, replay.run, 0), status: "done", stories, tickets });
  }
  return json({ detail: "Not found" }, 404);
}
