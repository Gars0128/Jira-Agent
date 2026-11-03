"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { costLabel, draftErrors, safeTraceUrl, statusInfo, steps } from "../lib/presentation";
import type { Capabilities, Project, Run, RunEvent, Story } from "../lib/types";
import { Arrow, EmptyState, Evidence, JiraBoard, TicketCard } from "./components";
import { StoryEditor } from "./story-editor";
import { ResultTabs, type ResultTab } from "./result-tabs";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { ...options, headers: { "Content-Type": "application/json", ...options?.headers }, cache: "no-store" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : payload?.error ?? `Request failed (${response.status}). Please try again.`);
  }
  return payload as T;
}

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [projectId, setProjectId] = useState("");
  const [presetId, setPresetId] = useState("");
  const [transcript, setTranscript] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [stories, setStories] = useState<Story[]>([]);
  const [tab, setTab] = useState<ResultTab>("requirements");
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [approving, setApproving] = useState(false);
  const draftRun = useRef<string | null>(null);
  const revealedRun = useRef<string | null>(null);
  const runRequest = useRef<AbortController | null>(null);
  const currentProject = projects.find((project) => project.id === projectId);
  const active = submitting || (!!runId && !run && !error) || run?.status === "queued" || run?.status === "running";
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
      if (saved) setRunId(saved);
    }).catch(() => { if (mounted) setError("The API is unavailable. Start the backend and reload this page."); })
      .finally(() => { if (mounted) setLoading(false); });
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
        setRun(snapshot); setError(null);
        if (snapshot.status === "awaiting_review" && draftRun.current !== runId) {
          setStories(snapshot.stories); draftRun.current = runId;
        }
        if (snapshot.status === "done") setStories(snapshot.stories);
        if (["done", "error", "awaiting_review"].includes(snapshot.status)) {
          source.close(); window.clearInterval(timer);
        }
      } catch (reason) {
        if (controller.signal.aborted) return;
        if (reason instanceof Error && reason.message === "Unknown run") { stopped = true; source.close(); window.clearInterval(timer); }
        setError(reason instanceof Error ? reason.message : "Could not refresh this run.");
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

  useEffect(() => {
    if (run?.status !== "awaiting_review" || revealedRun.current === run.run_id) return;
    revealedRun.current = run.run_id;
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [run?.status, run?.run_id]);

  async function startRun() {
    runRequest.current?.abort(); setRunId(null); setError(null); setSubmitting(true); setEvents([]); setSelected(null); setRun(null); setStories([]); setTab("requirements"); draftRun.current = null;
    try {
      const result = await request<{ run_id: string }>("/runs", { method: "POST", body: JSON.stringify({ project_id: projectId, transcript, ...(presetId ? { preset_id: presetId } : {}) }) });
      setRunId(result.run_id);
      window.history.replaceState(null, "", `?run=${encodeURIComponent(result.run_id)}`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start the run."); }
    finally { setSubmitting(false); }
  }

  async function approve() {
    if (!run || !capabilities || approving) return;
    const errors = draftErrors(stories, run.requirements.filter((item) => item.status === "new").map((item) => item.id));
    if (errors.length) { setError(errors.join(" ")); return; }
    setApproving(true); setError(null);
    try {
      const current = await request<Capabilities>("/capabilities");
      if (current.jira_dry_run !== capabilities.jira_dry_run) throw new Error("Jira mode changed. Reload the page and review the current mode before approving.");
      setTab("preview");
      const result = await request<Run>(`/runs/${run.run_id}/approve`, { method: "POST", body: JSON.stringify({ stories }) });
      setRun(result); setStories(result.stories); setTab("preview");
    } catch (reason) { setTab("stories"); setError(reason instanceof Error ? reason.message : "Approval failed. Your edits are still here."); }
    finally { setApproving(false); }
  }

  const requirements = run?.requirements ?? [];
  const selectedRequirement = requirements.find((item) => item.id === selected);
  const doneNodes = new Set(events.filter((event) => event.type === "node_finished").map((event) => event.node));
  const currentNode = events.filter((event) => event.type === "node_started").at(-1)?.node;
  const review = run?.status === "awaiting_review";
  const completed = run?.status === "done";
  const progress = completed ? steps.length : review ? 5 : steps.filter((step) => doneNodes.has(step.id)).length;
  const counts = (Object.keys(statusInfo) as (keyof typeof statusInfo)[]).map((status) => ({ status, count: requirements.filter((item) => item.status === status).length })).filter((item) => item.count);
  const statusText = completed ? "Completed" : review ? "Your review is ready" : run?.status === "error" ? "Needs attention" : active ? "Agent is working" : "Ready when you are";

  return <div className="workspace">
    <a href="#main" className="skip-link">Skip to workspace</a>
    <div className="main-shell">
      <header className="appbar">
        <Link className="brand" href="/" aria-label="Tiro home"><svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="currentColor" /><path d="M9.5 10h13M16 10v12.5" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" /><circle cx="23.5" cy="22" r="2.2" fill="#ff8a5c" /></svg><span>Tiro<span className="brand-sub">call to Jira</span></span></Link>
        <nav aria-label="Sections"><a href="#main">Studio</a><a href="#pipeline">Workflow</a><a href="#results">Results</a></nav>
        <span className={`mode-pill ${capabilities?.jira_dry_run === false ? "live" : ""}`} title="Nothing reaches Jira until you approve"><i />{!capabilities ? "Checking mode…" : capabilities.replay ? "Recorded demo" : dryRun ? "Preview · dry run" : "Live Jira"}</span>
      </header>
      <main id="main">
        <div className="page-heading"><div><div className="eyebrow"><span /> CONVERSATIONS, WITH DIRECTION</div><h1>From conversation<br className="mobile-break" /> to clarity<span>.</span></h1><p>Paste a client call. Get Jira stories backed by real quotes.</p></div><span className="heading-index">DISCOVERY / 001</span></div>
        <ol className="how-it-works reveal-list" aria-label="How it works">
          <li><span>1</span><div><strong>Pick a call</strong>Use a sample or paste your own.</div></li>
          <li><span>2</span><div><strong>The agent reads it</strong>Keeps real requests, drops small talk.</div></li>
          <li><span>3</span><div><strong>You approve</strong>Edit the stories, send them to Jira.</div></li>
        </ol>

        {error && <div className="error-banner" role="alert"><span>{error}</span><button type="button" onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}

        <div className="studio-grid">
          <section className="panel input-panel" aria-labelledby="source-heading">
            <div className="panel-heading"><div><span className="section-number">01</span><h2 id="source-heading">Start with a conversation</h2></div><span className="tag">SOURCE</span></div>
            <div className="input-body">
              <div className="source-selectors"><label>Project<select value={projectId} disabled={loading || active} onChange={(event) => { const project = projects.find((item) => item.id === event.target.value); setProjectId(event.target.value); setPresetId(project?.transcripts[0]?.id ?? ""); setTranscript(project?.transcripts[0]?.text ?? ""); }}>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
              <label>Conversation<select value={presetId} disabled={loading || active} onChange={(event) => { const preset = currentProject?.transcripts.find((item) => item.id === event.target.value); setPresetId(event.target.value); if (preset) setTranscript(preset.text); }}><option value="">✎ Write your own</option>{currentProject?.transcripts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
              {capabilities?.replay && <p className="mode-hint"><strong>Recorded demo.</strong> This hosted version replays real runs of the two samples. Clone the repo to analyze your own calls.</p>}
              {currentProject?.spec === false && <p className="mode-hint"><strong>Any conversation.</strong> Paste a call, get clean stories. Without a spec, conflicts aren’t checked.</p>}
              <div className="transcript-label"><label htmlFor="transcript">Transcript</label><span>Fictional data only</span></div>
              <textarea id="transcript" className="transcript" value={transcript} maxLength={20000} disabled={active} placeholder={loading ? "Loading your workspace…" : "Paste a fictional client conversation here. Include speaker names and the original wording."} onChange={(event) => { setTranscript(event.target.value); setPresetId(""); }} />
              <div className="input-footer"><span>{transcript.length.toLocaleString()} / 20,000 characters</span><span>Quotes stay verbatim <span aria-hidden="true">↳</span></span></div>
              <button type="button" className="primary-button run-button" disabled={loading || active || approving || !projectId || !transcript.trim()} onClick={() => void startRun()}>{active ? <><span className="spinner" /> Analyzing conversation</> : <>Run discovery <Arrow /></>}</button>
              <p className="under-button">Nothing is sent to Jira until you review and approve.</p>
            </div>
          </section>

          <section className="panel pipeline-panel" id="pipeline" aria-labelledby="pipeline-heading">
            <div className="panel-heading"><div><span className="section-number">02</span><h2 id="pipeline-heading">The agent workflow</h2></div><span className={`live-indicator ${active ? "working" : ""}`}><i />{active ? "LIVE" : "LANGGRAPH"}</span></div>
            <div className="pipeline-status"><span className={`status-dot ${review || completed ? "success" : active ? "working" : ""}`} /><div><strong>{statusText}</strong><span>{review ? "Your decisions shape the final output." : completed ? "Approved stories are ready to hand off." : "Every step is visible. Every decision has context."}</span></div></div>
            <div className="progress-track" role="progressbar" aria-label="Workflow progress" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={progress}><span style={{ width: `${(progress / steps.length) * 100}%` }} /></div>
            <ol className="pipeline-list">{steps.map((step, index) => {
              const done = completed || (review && index < 5) || doneNodes.has(step.id);
              const running = active && currentNode === step.id || review && index === 5;
              return <li key={step.id} className={`${done ? "step-done" : ""} ${running ? "step-current" : ""}`}><span className="step-icon" aria-hidden="true">{done ? "✓" : String(index + 1).padStart(2, "0")}</span><div><strong>{step.label}</strong><span>{step.detail}</span></div>{running && <span className="step-pill">{review ? "YOU" : "RUNNING"}</span>}</li>;
            })}</ol>
            <div className="run-metrics"><div><span>RUN COST</span><strong>{costLabel(run?.usage?.cost_usd)}</strong></div><div><span>ELAPSED</span><strong>{run?.latency_ms ? `${(run.latency_ms / 1000).toFixed(1)}s` : "—"}</strong></div><div><span>TRACE</span>{traceUrl ? <a href={traceUrl} target="_blank" rel="noreferrer">LangSmith <Arrow diagonal /></a> : <strong className="muted">—</strong>}</div></div>
          </section>
        </div>

        <section className="results-section" id="results" aria-labelledby="results-heading">
          <div className="results-heading"><div><div className="eyebrow">THE WORK, MADE VISIBLE</div><h2 id="results-heading">Evidence before action.</h2></div>{runId && <span className="run-id" title={runId}>RUN / {runId.slice(0, 8)}</span>}</div>
          {!!counts.length && <ul className="summary-strip reveal-list" aria-label="What the agent found">{counts.map(({ status, count }) => <li key={status} className={`summary-${status}`}><strong>{count}</strong><div><span>{statusInfo[status].label}</span>{statusInfo[status].meaning}</div></li>)}</ul>}
          <ResultTabs selected={tab} onChange={setTab} counts={[requirements.length, stories.length, run?.tickets?.length ?? 0]} />
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="results-body fade-in" key={tab}>
            {tab === "requirements" && (requirements.length ? <div className="requirements-grid"><div className="requirement-list reveal-list">{requirements.map((item) => <button type="button" key={item.id} className={`requirement-card ${selected === item.id ? "selected" : ""}`} onClick={() => setSelected(item.id)} aria-expanded={selected === item.id}><div className="card-eyebrow"><span>{item.id} <span className="priority">/ {item.priority}</span></span><span className={`badge badge-${item.status ?? "pending"}`}>{item.status ? statusInfo[item.status].label : "Pending"}</span></div><h3>{item.text}</h3><blockquote>“{item.quote}”</blockquote><div className="requirement-footer"><span>{item.speaker}</span><span>Inspect evidence <Arrow /></span></div></button>)}</div><Evidence key={selectedRequirement?.id ?? requirements[0].id} requirement={selectedRequirement ?? requirements[0]} run={run!} /></div> : <EmptyState working={active} symbol="↳" title={active ? "Reading the conversation…" : "Good decisions start with evidence."} text="Run a conversation to see grounded requirements, original quotes, and specification references here." />)}
            {tab === "stories" && <>{stories.length ? <div className="stories-grid reveal-list">{stories.map((story, index) => <StoryEditor key={story.id} story={story} editable={review && !approving} onChange={(changed) => setStories((previous) => previous.map((item, itemIndex) => itemIndex === index ? changed : item))} />)}</div> : <EmptyState symbol="≡" title="From requirements to something buildable." text={review ? "No new requirements need implementation stories. Review the open questions below." : "The agent drafts stories for new requirements and checks their acceptance criteria. Your edits stay in your hands."} />}
              {!!run?.questions?.length && <aside className="questions"><div className="eyebrow">DECISIONS TO MAKE</div><h3>Open questions</h3><ul>{run.questions.map((question, index) => <li key={index}>{question}</li>)}</ul></aside>}
              {review && <div className="approval-bar"><div><strong>Your review is the final checkpoint.</strong><span>Approve these {stories.length} stories to {dryRun ? "generate the Jira preview." : "create live Jira tickets."}</span></div><button type="button" className="primary-button" disabled={approving || !capabilities} onClick={() => void approve()}>{approving ? "Approving…" : dryRun ? "Approve & preview" : "Approve & create tickets"}<Arrow /></button></div>}</>}
            {tab === "preview" && (run?.status === "error" ? <EmptyState symbol="!" title="Tickets were not created." text={`${run.error ?? "Jira did not accept the tickets."} Fix the configuration, then start a new run.`} /> : approving ? <div className="preview"><JiraBoard stories={stories} live={!dryRun} /></div> : completed ? <div className="preview"><div className="preview-heading"><span className="check-circle">✓</span><div><h3>Reviewed. Approved. Ready.</h3><p>{run?.tickets?.every((ticket) => ticket.dry_run) ? "This run shows Jira payloads without creating live tickets." : "Approved stories were handed off to Jira."}</p></div></div><JiraBoard stories={stories} tickets={run?.tickets} live={!dryRun} />{run?.tickets?.length ? <div className="ticket-list reveal-list">{run.tickets.map((ticket, index) => <TicketCard key={index} ticket={ticket} story={stories[index]} />)}</div> : <p className="muted">No implementation tickets were needed for this conversation.</p>}</div> : <EmptyState symbol="↗" title="A handoff you can trust." text="Review the user stories, make your edits, then approve. Your Jira preview will appear here." />)}
          </div>
          {review && tab === "requirements" && <div className="review-nudge"><span><strong>The groundwork is done.</strong> Your stories are ready for a human review.</span><button type="button" onClick={() => setTab("stories")}>Review stories <Arrow /></button></div>}
          {run?.status === "error" && <div className="error-banner" role="alert">{run.error ?? "This run could not complete. Check the configuration and start a new run."}</div>}
        </section>
        <footer className="page-footer"><span>TIRO <span className="footer-arrow">·</span> CALL → JIRA</span><span>Grounded in evidence. Guided by you.</span><span>Fictional data · Human-approved output</span></footer>
      </main>
    </div>
  </div>;
}

