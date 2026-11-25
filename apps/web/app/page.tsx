"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { costLabel, draftErrors, followUps, safeTraceUrl, sectionTitle, steps } from "../lib/presentation";
import type { Capabilities, Project, Run, RunEvent, Story } from "../lib/types";
import { Arrow, TicketBoard, type BoardCard } from "./components";
import { StoryEditor } from "./story-editor";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: { "Content-Type": "application/json", ...options?.headers }, cache: "no-store" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : payload?.error ?? `Request failed (${response.status}). Please try again.`);
  }
  return payload as T;
}

// Each phase carries only the data that exists in it, so impossible combinations can't be written.
type Phase =
  | { kind: "loading" }
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "running"; runId: string; run: Run | null }
  | { kind: "review"; run: Run }
  | { kind: "approving"; run: Run }
  | { kind: "done"; run: Run }
  | { kind: "error"; message: string; run?: Run };

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [projectId, setProjectId] = useState("");
  const [presetId, setPresetId] = useState("");
  const [transcript, setTranscript] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [stories, setStories] = useState<Story[]>([]);
  // A request that failed while the run itself is fine (e.g. approval refused); the run keeps its phase.
  const [notice, setNotice] = useState<string | null>(null);
  const draftRun = useRef<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [openCard, setOpenCard] = useState<number | null>(null);
  const revealedRun = useRef<string | null>(null);
  const followNewRun = useRef(false);
  const runRequest = useRef<AbortController | null>(null);
  const currentProject = projects.find((project) => project.id === projectId);
  const run = "run" in phase ? phase.run ?? null : null;
  const runId = phase.kind === "running" ? phase.runId : null;
  const loading = phase.kind === "loading";
  const active = phase.kind === "submitting" || phase.kind === "running";
  const approving = phase.kind === "approving";
  const dryRun = capabilities?.jira_dry_run === true;
  const traceUrl = safeTraceUrl(run?.trace_url);

  useEffect(() => {
    let mounted = true;
    Promise.all([request<{ projects: Project[] }>("/projects"), request<Capabilities>("/capabilities")]).then(([data, configuration]) => {
      if (!mounted) return;
      setCapabilities(configuration);
      setProjects(data.projects);
      const first = data.projects[0];
      if (first) {
        setProjectId(first.id);
        setPresetId(first.transcripts[0]?.id ?? "");
        setTranscript(first.transcripts[0]?.text ?? "");
      }
      const saved = new URLSearchParams(window.location.search).get("run");
      setPhase(saved ? { kind: "running", runId: saved, run: null } : { kind: "idle" });
    }).catch(() => { if (mounted) setPhase({ kind: "error", message: "The API is unavailable. Start the backend and reload this page." }); });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!runId) return;
    let stopped = false;
    let inFlight = false;
    const controller = new AbortController();
    runRequest.current = controller;
    const path = `/runs/${encodeURIComponent(runId)}`;
    const source = new EventSource(`/api${path}/events`);
    const reload = async () => {
      if (inFlight || stopped) return;
      inFlight = true;
      try {
        const snapshot = await request<Run>(path, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setNotice(null);
        if (snapshot.status === "awaiting_review") {
          // SSE and polling can both deliver the review; only the first one seeds the editable draft.
          if (draftRun.current !== runId) { setStories(snapshot.stories); draftRun.current = runId; }
          setPhase({ kind: "review", run: snapshot });
        } else if (snapshot.status === "done") {
          setStories(snapshot.stories); setPhase({ kind: "done", run: snapshot });
        } else if (snapshot.status === "error") {
          setPhase({ kind: "error", message: snapshot.error ?? "This run could not complete. Check the configuration and start a new run.", run: snapshot });
        } else setPhase({ kind: "running", runId, run: snapshot });
        if (["done", "error", "awaiting_review"].includes(snapshot.status)) {
          source.close(); window.clearInterval(timer);
        }
      } catch (reason) {
        if (controller.signal.aborted) return;
        const message = reason instanceof Error ? reason.message : "Could not refresh this run.";
        if (message === "Unknown run") { stopped = true; source.close(); window.clearInterval(timer); setPhase({ kind: "error", message }); }
        else setNotice(message);
      } finally { inFlight = false; }
    };
    source.onmessage = (message) => {
      if (stopped) return;
      try {
        const event = JSON.parse(message.data) as RunEvent;
        setEvents((previous) => [...previous.slice(-39), event]);
        void reload();
      } catch { /* Polling below recovers from a malformed or interrupted event. */ }
    };
    source.onerror = () => source.close();
    void reload();
    const timer = window.setInterval(() => { if (!stopped) void reload(); }, 2000);
    return () => { stopped = true; controller.abort(); source.close(); window.clearInterval(timer); };
  }, [runId]);

  // Follow a run started here (not one restored from the URL): the results section renders with its runId.
  useEffect(() => {
    if (!runId || !followNewRun.current) return;
    followNewRun.current = false;
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [runId]);

  useEffect(() => {
    if (run?.status !== "awaiting_review" || revealedRun.current === run.run_id) return;
    revealedRun.current = run.run_id;
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [run?.status, run?.run_id]);

  async function startRun() {
    runRequest.current?.abort(); setNotice(null); setPhase({ kind: "submitting" }); setEvents([]); setStories([]); draftRun.current = null;
    try {
      const result = await request<{ run_id: string }>("/runs", { method: "POST", body: JSON.stringify({ project_id: projectId, transcript, ...(presetId ? { preset_id: presetId } : {}) }) });
      setPhase({ kind: "running", runId: result.run_id, run: null });
      window.history.replaceState(null, "", `?run=${encodeURIComponent(result.run_id)}`);
      followNewRun.current = true;
    } catch (reason) { setPhase({ kind: "idle" }); setNotice(reason instanceof Error ? reason.message : "Could not start the run."); }
  }

  async function approve() {
    if (phase.kind !== "review" || !capabilities) return;
    const reviewed = phase.run;
    const errors = draftErrors(stories, reviewed.requirements.filter((item) => item.status === "new").map((item) => item.id));
    if (errors.length) { setNotice(errors.join(" ")); return; }
    setPhase({ kind: "approving", run: reviewed }); setNotice(null);
    try {
      const current = await request<Capabilities>("/capabilities");
      if (current.jira_dry_run !== capabilities.jira_dry_run) throw new Error("Jira mode changed. Reload the page and review the current mode before approving.");
      const result = await request<Run>(`/runs/${reviewed.run_id}/approve`, { method: "POST", body: JSON.stringify({ stories }) });
      setStories(result.stories); setPhase({ kind: "done", run: result });
      document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (reason) { setPhase({ kind: "review", run: reviewed }); setNotice(reason instanceof Error ? reason.message : "Approval failed. Your edits are still here."); }
  }

  const requirements = run?.requirements ?? [];
  const doneNodes = new Set(events.filter((event) => event.type === "node_finished").map((event) => event.node));
  const currentNode = events.filter((event) => event.type === "node_started").at(-1)?.node;
  const review = phase.kind === "review" || approving;
  const completed = phase.kind === "done";
  const showResults = run !== null || phase.kind === "running";
  const progress = completed ? steps.length : review ? 5 : steps.filter((step) => doneNodes.has(step.id)).length;
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  const sorted = requirements.some((item) => item.status);
  const specTitles = (item: { id: string; spec_refs: string[] }) => (run?.retrieved?.[item.id] ?? []).filter((chunk) => item.spec_refs.includes(chunk.id)).map((chunk) => sectionTitle(chunk.text) ?? chunk.id);
  // Stories first, then decisions and questions: the same order the API creates them in.
  const drafts: BoardCard[] = review || completed ? [
    ...stories.map((story) => { const source = requirements.find((item) => story.requirement_ids.includes(item.id)); return { kind: "story" as const, title: story.title, quote: source?.quote, speaker: source?.speaker, specs: [], story }; }),
    ...followUps(requirements).map(({ kind, summary, requirement }) => ({ kind, title: summary, quote: requirement.quote, speaker: requirement.speaker, why: requirement.note, specs: specTitles(requirement) })),
  ] : [];
  const cards = drafts.map((card, index) => ({ ...card, ticket: run?.tickets?.[index] }));
  const skipped = requirements.filter((item) => item.status === "duplicate");
  const heading = !review && !completed ? "Working on it" : completed ? (cards.length ? "Done" : "Review finished") : cards.length ? `${plural(cards.length, "ticket", "tickets")} from this call` : "No tickets from this call";
  const stage = !requirements.length ? "Reading the call…" : !sorted ? `Found ${plural(requirements.length, "request", "requests")}. Checking them against the spec…` : "Writing tickets…";
  const statusText = completed ? "Completed" : review ? "Your review is ready" : phase.kind === "error" ? "Needs attention" : active ? "Agent is working" : "Ready when you are";

  return <div className="workspace">
    <a href="#main" className="skip-link">Skip to workspace</a>
    <div className="main-shell">
      <header className="appbar">
        <Link className="brand" href="/"><svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="currentColor" /><path d="M9.5 10h13M16 10v12.5" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" /><circle cx="23.5" cy="22" r="2.2" fill="#ff8a5c" /></svg><span>Tiro<span className="brand-sub">call to Jira</span></span></Link>
        <nav aria-label="Sections"><a href="#main">Studio</a><a href="#pipeline">Workflow</a>{showResults && <a href="#results">Results</a>}</nav>
        <span className={`mode-pill ${capabilities?.jira_dry_run === false ? "live" : ""}`} title="Nothing reaches Jira until you approve"><i />{!capabilities ? "Checking mode…" : capabilities.replay ? "Recorded demo" : dryRun ? "Preview · dry run" : "Live Jira"}</span>
      </header>
      <main id="main">
        <div className="page-heading"><div><h1>From conversation<br className="mobile-break" /> to clarity<span>.</span></h1><p>Paste a client call. Get Jira tickets backed by the client’s own words.</p></div></div>
        <ol className="how-it-works reveal-list" aria-label="How it works">
          <li><span>1</span><div><strong>Pick a call</strong>Use a sample or paste your own.</div></li>
          <li><span>2</span><div><strong>The agent reads it</strong>Keeps real requests, drops small talk.</div></li>
          <li><span>3</span><div><strong>You approve</strong>Edit the tickets, then send them to Jira.</div></li>
        </ol>

        {notice && <div className="error-banner" role="alert"><span>{notice}</span><button type="button" onClick={() => setNotice(null)} aria-label="Dismiss error">×</button></div>}
        {phase.kind === "error" && !phase.run && <div className="error-banner" role="alert"><span>{phase.message}</span><button type="button" onClick={() => setPhase({ kind: "idle" })} aria-label="Dismiss error">×</button></div>}

        <div className="studio-grid">
          <section className="panel input-panel" aria-labelledby="source-heading">
            <div className="panel-heading"><div><span className="section-number">01</span><h2 id="source-heading">Start with a conversation</h2></div><span className="tag">SOURCE</span></div>
            <div className="input-body">
              <div className="source-selectors"><label>Project<select value={projectId} disabled={loading || active} onChange={(event) => { const project = projects.find((item) => item.id === event.target.value); setProjectId(event.target.value); setPresetId(project?.transcripts[0]?.id ?? ""); setTranscript(project?.transcripts[0]?.text ?? ""); }}>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
              <label>Conversation<select value={presetId} disabled={loading || active} onChange={(event) => { const preset = currentProject?.transcripts.find((item) => item.id === event.target.value); setPresetId(event.target.value); if (preset) setTranscript(preset.text); }}><option value="">✎ Write your own</option>{currentProject?.transcripts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
              {capabilities?.replay && <p className="mode-hint"><strong>Recorded demo.</strong> This hosted version replays real runs of seven sample calls. Clone the repo to analyze your own calls.</p>}
              {currentProject?.spec === true && !capabilities?.replay && <p className="mode-hint"><strong>With a spec.</strong> The spec is what the client already agreed to. Tiro checks every request against it and flags anything new, repeated or contradictory.</p>}
              {currentProject?.spec === false && <p className="mode-hint"><strong>Any conversation.</strong> Paste a call, get clean stories. Without a spec, conflicts aren’t checked.</p>}
              <div className="transcript-label"><label htmlFor="transcript">Transcript</label><span>Fictional data only</span></div>
              <textarea id="transcript" className="transcript" value={transcript} maxLength={20000} disabled={active} placeholder={loading ? "Loading your workspace…" : "Paste a fictional client conversation here. Include speaker names and the original wording."} onChange={(event) => { setTranscript(event.target.value); setPresetId(""); }} />
              <div className="input-footer"><span>{transcript.length.toLocaleString()} / 20,000 characters</span><span>Quotes stay verbatim <span aria-hidden="true">↳</span></span></div>
              <button type="button" className="primary-button run-button" disabled={loading || active || approving || !projectId || !transcript.trim()} onClick={() => void startRun()}>{active ? <><span className="spinner" /> Analyzing conversation</> : <>Run discovery <Arrow /></>}</button>
              <p className="under-button">Nothing is sent to Jira until you review and approve.</p>
            </div>
          </section>

          <section className="panel pipeline-panel" id="pipeline" aria-labelledby="pipeline-heading">
            <div className="panel-heading"><div><span className="section-number">02</span><h2 id="pipeline-heading">What the agent does</h2></div>{active && <span className="live-indicator working"><i />LIVE</span>}</div>
            <div className="pipeline-status"><span className={`status-dot ${review || completed ? "success" : active ? "working" : ""}`} /><div><strong>{statusText}</strong><span>{review ? "Your decisions shape the final output." : completed ? "Approved stories are ready to hand off." : "Every step is visible. Every decision has context."}</span></div></div>
            <div className="progress-track" role="progressbar" aria-label="Workflow progress" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={progress}><span style={{ width: `${(progress / steps.length) * 100}%` }} /></div>
            <ol className="pipeline-list">{steps.map((step, index) => {
              const done = completed || (review && index < 5) || doneNodes.has(step.id);
              const running = active && currentNode === step.id || review && index === 5;
              return <li key={step.id} className={`${done ? "step-done" : ""} ${running ? "step-current" : ""}`}><span className="step-icon" aria-hidden="true">{done ? "✓" : String(index + 1).padStart(2, "0")}</span><div><strong>{step.label}</strong><span>{step.detail}</span></div>{running && <span className="step-pill">{review ? "YOU" : "RUNNING"}</span>}</li>;
            })}</ol>
            <dl className="run-metrics">
              <div><dt>Cost</dt><dd>{costLabel(run?.usage?.cost_usd)}</dd></div>
              <div><dt>Tokens</dt><dd>{run?.usage?.input_tokens ? <>{run.usage.input_tokens.toLocaleString("en")} in · {(run.usage.output_tokens ?? 0).toLocaleString("en")} out</> : "—"}</dd></div>
              <div><dt>Model calls</dt><dd>{run?.usage?.calls || "—"}</dd></div>
              <div><dt>Time</dt><dd>{run?.latency_ms ? `${(run.latency_ms / 1000).toFixed(1)}s` : "—"}</dd></div>
            </dl>
            <p className="run-source">{run?.cached ? "This sample was analyzed before, so the saved result was reused: no model calls." : capabilities?.replay ? `Recorded run on ${capabilities.model}. Tokens are what the provider reported, including the spec-search embeddings; cost is tokens × list price. The run’s LangSmith trace carries the same numbers as metadata.` : capabilities?.model ? `Model: ${capabilities.model}. Tokens as reported by the provider, including embeddings; cost is tokens × configured price.` : null}{traceUrl && <> <a href={traceUrl} target="_blank" rel="noreferrer">Open the full trace in LangSmith <Arrow diagonal /></a></>}</p>
          </section>
        </div>

        {showResults && <section className="results-section" id="results" aria-labelledby="results-heading" aria-busy={active}>
          <div className="results-heading"><h2 id="results-heading">{heading}</h2></div>
          <p className="results-summary" aria-live="polite">{active || (!review && !completed) ? stage : completed ? (!cards.length ? "Nothing was sent to Jira." : run?.tickets?.every((ticket) => ticket.dry_run) ? "Preview mode: this is exactly what Jira would receive. Nothing was sent." : "Your tickets are in Jira.") : `${plural(requirements.length, "request", "requests")} found in the call. Edit anything, then approve.`}</p>
          {!!skipped.length && (review || completed) && <details className="skipped"><summary>{plural(skipped.length, "request was", "requests were")} already in the spec, so no ticket</summary><ul>{skipped.map((item) => <li key={item.id}>{item.text} <cite>“{item.quote}”</cite></li>)}</ul></details>}
          {!!cards.length && <TicketBoard cards={cards} creating={approving} live={!dryRun} onOpen={(index) => { setOpenCard(index); dialog.current?.showModal(); }} />}
          <dialog ref={dialog} className="ticket-dialog" aria-labelledby="dialog-title" onClose={() => setOpenCard(null)}>{(() => {
            const card = openCard === null ? undefined : cards[openCard];
            if (!card) return null;
            const index = stories.findIndex((story) => story.id === card.story?.id);
            return <>
              <header><span className={`issue-type kind-${card.kind}`} aria-hidden="true" /><h3 id="dialog-title">{card.title}</h3><button type="button" className="dialog-close" onClick={() => dialog.current?.close()} aria-label="Close">×</button></header>
              {card.quote && <blockquote>“{card.quote}”{card.speaker && <cite> — {card.speaker}</cite>}</blockquote>}
              {card.story ? <StoryEditor story={card.story} basedOn={card.story.requirement_ids.map((id) => requirements.find((item) => item.id === id)?.text ?? id)} editable={review && !approving} onChange={(changed) => setStories((previous) => previous.map((item, itemIndex) => itemIndex === index ? changed : item))} />
                : <div className="dialog-why"><h4>Why</h4><p>{card.why ?? "No reason was given."}</p>{!!card.specs.length && <p className="muted">From the spec: {card.specs.join(", ")}</p>}</div>}
              <footer><button type="button" className="primary-button" onClick={() => dialog.current?.close()}>{card.story && review ? "Save" : "Close"}</button></footer>
            </>;
          })()}</dialog>
          {review && <div className="approval-bar"><div>{cards.length ? <><strong>Ready to create {plural(cards.length, "ticket", "tickets")}.</strong><span>Nothing is sent until you approve.</span></> : <><strong>Nothing to send to Jira.</strong><span>Every request is already in the spec.</span></>}</div><button type="button" className="primary-button" disabled={approving || !capabilities} onClick={() => void approve()}>{approving ? "Creating…" : !cards.length ? "Finish review" : dryRun ? `Create ${plural(cards.length, "ticket", "tickets")} (preview)` : `Create ${plural(cards.length, "ticket", "tickets")} in Jira`}<Arrow /></button></div>}
          {phase.kind === "error" && phase.run && <div className="error-banner" role="alert">{phase.message}</div>}
        </section>}
        <footer className="page-footer"><span>TIRO <span className="footer-arrow">·</span> CALL → JIRA</span><span>Grounded in evidence. Guided by you.</span><span>Fictional data · Human-approved output</span></footer>
      </main>
    </div>
  </div>;
}

