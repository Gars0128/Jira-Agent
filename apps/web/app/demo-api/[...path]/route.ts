// Recorded-run replay for the hosted demo (DEMO_REPLAY=true). It mimics the API
// contract with seven real stored runs, so the site works without a backend,
// model calls or Jira writes. Locally, /api goes to the real FastAPI service.
import recording from "../../../demo/runs.json";
import type { Run, Story } from "../../../lib/types";

type Recorded = Omit<Run, "run_id" | "status" | "tickets" | "error" | "trace_url">;
const runs = recording.runs as unknown as Record<string, Recorded>;

// Seconds after creation at which each node finishes; review follows the last.
const schedule: [string, number][] = [["extract", 2.4], ["retrieve_spec", 3.4], ["classify", 5.2], ["write_stories", 7.6], ["critic", 9]];
const reviewAt = 9.4;

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { "Cache-Control": "no-store" } });

function parseRun(id: string): { key: string; started: number } | null {
  // Run IDs avoid "/" because the UI puts them in URL paths unencoded on approve.
  const match = /^replay~([\w-]+):([\w-]+)~(\d+)$/.exec(id);
  const key = match && `${match[1]}/${match[2]}`;
  if (!match || !key || !(key in runs)) return null;
  return { key, started: Number(match[3]) };
}

function snapshot(id: string, key: string, started: number): Run {
  const run = runs[key];
  const elapsed = (Date.now() - started) / 1000;
  const done = (node: string) => elapsed >= schedule.find(([name]) => name === node)![1];
  const base = { run_id: id, trace_url: null, tickets: [], error: null, usage: run.usage, latency_ms: run.latency_ms, questions: run.questions };
  if (elapsed >= reviewAt) return { ...base, ...run, run_id: id, status: "awaiting_review", trace_url: null, tickets: [], error: null };
  return {
    ...base,
    status: "running",
    requirements: done("extract") ? run.requirements.map((item) => (done("classify") ? item : { ...item, status: null, spec_refs: [], note: null })) : [],
    retrieved: done("retrieve_spec") ? run.retrieved : {},
    stories: done("write_stories") ? run.stories : [],
    questions: done("classify") ? run.questions : [],
    usage: { ...run.usage, cost_usd: null },
    latency_ms: 0,
  };
}

function events(started: number): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: object) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      let previous = 0;
      for (const [node, finishedAt] of schedule) {
        const wait = started + previous * 1000 - Date.now();
        if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
        send({ type: "node_started", node });
        const finish = started + finishedAt * 1000 - Date.now();
        if (finish > 0) await new Promise((resolve) => setTimeout(resolve, finish));
        send({ type: "node_finished", node });
        previous = finishedAt;
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
  if (path.join("/") === "capabilities") return json({ public_demo: true, jira_dry_run: true, transcript_limit: 20000, replay: true });
  if (path.join("/") === "projects") return json({ projects: recording.projects });
  if (path.join("/") === "health" || path.join("/") === "ready") return json({ status: "ok" });
  if (path[0] === "runs" && path[1]) {
    const run = parseRun(path[1]);
    if (!run) return json({ detail: "Unknown run" }, 404);
    if (path[2] === "events") return events(run.started);
    if (path.length === 2) return json(snapshot(path[1], run.key, run.started));
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
  if (path[0] === "runs" && path[2] === "approve") {
    const run = parseRun(path[1]);
    if (!run) return json({ detail: "Unknown run" }, 404);
    const stories = (Array.isArray(body?.stories) ? body.stories : []).slice(0, 30) as Story[];
    // A short pause lets the board show "Creating…" as it would with Jira.
    await new Promise((resolve) => setTimeout(resolve, 1800));
    const tickets = stories.map((story) => ({ key: `PREVIEW-${String(story.idempotency_key).slice(0, 8)}`, dry_run: true, reused: false, fields: { summary: String(story.title) } }));
    return json({ ...snapshot(path[1], run.key, 0), status: "done", stories, tickets });
  }
  return json({ detail: "Not found" }, 404);
}
