import { safeJiraUrl, sectionTitle } from "../lib/presentation";
import type { Requirement, Run, Story, Ticket } from "../lib/types";

export function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <span aria-hidden="true">{diagonal ? "↗" : "→"}</span>;
}

export function EmptyState({ symbol, title, text, working = false }: { symbol: string; title: string; text: string; working?: boolean }) {
  return <div className={`empty-state ${working ? "working" : ""}`}><span className="empty-symbol" aria-hidden="true">{symbol}</span><h3>{title}</h3><p>{text}</p></div>;
}

export function Evidence({ requirement, run }: { requirement: Requirement; run: Run }) {
  const chunks = run.retrieved?.[requirement.id] ?? [];
  return <aside className="evidence-panel"><div className="eyebrow">EVIDENCE</div><h3>Why Tiro marked it this way</h3><p className="evidence-note">{requirement.note ?? "No classification rationale was provided."}</p><div className="evidence-source"><span className="field-label">Original client quote</span><blockquote><mark>{requirement.quote}</mark></blockquote><span className="muted">— {requirement.speaker}</span></div><h4>Spec sections it checked <span>{chunks.length}</span></h4>{chunks.map((chunk) => <details key={chunk.id} open={requirement.spec_refs.includes(chunk.id)}><summary><span>{sectionTitle(chunk.text) ?? chunk.id}</span>{requirement.spec_refs.includes(chunk.id) && <span className="cited">USED</span>}</summary><p>{chunk.text.replace(/^#.*\n+/, "")}</p></details>)}{!chunks.length && <p className="muted">This project has no spec, so nothing was checked.</p>}</aside>;
}

export function TicketCard({ ticket, story, basedOn = [] }: { ticket: Ticket; story?: Story; basedOn?: string[] }) {
  const url = safeJiraUrl(ticket.url);
  return <article className="ticket-card">
    <header><span className="ticket-type" aria-hidden="true">▮</span><span className="ticket-key">{ticket.dry_run ? "Preview" : ticket.key}</span>{ticket.dry_run ? <span className="tag">PREVIEW</span> : <span className="tag tag-live">{ticket.reused ? "ALREADY IN JIRA" : "CREATED"}</span>}{url && <a href={url} target="_blank" rel="noreferrer">Open in Jira <Arrow diagonal /></a>}</header>
    <h3>{ticket.fields?.summary ?? story?.title ?? "Approved story"}</h3>
    {story && <><p className="ticket-sentence">As a <strong>{story.as_a}</strong>, I want <strong>{story.i_want}</strong>, so that <strong>{story.so_that}</strong>.</p>
      <span className="field-label">Acceptance criteria</span><ul>{story.acceptance_criteria.map((item, index) => <li key={index}>{item}</li>)}</ul>
      {!!basedOn.length && <footer>Based on: {basedOn.join(" · ")}</footer>}</>}
    {ticket.fields && <details><summary>Exact data sent to Jira</summary><pre>{JSON.stringify(ticket.fields, null, 2)}</pre></details>}
  </article>;
}

export function JiraBoard({ stories, tickets, live }: { stories: Story[]; tickets?: Ticket[]; live: boolean }) {
  if (!stories.length || (tickets && !tickets.length)) return null;
  const status = tickets ? (live ? "Created in Jira" : "Dry run · nothing was sent") : (live ? "Creating tickets in Jira…" : "Preparing the preview…");
  return <section className="jira-board" aria-label="Jira board" aria-busy={!tickets}>
    <header><strong>Jira board</strong><span className={tickets ? "jira-status-done" : "jira-status-busy"}><i />{status}</span></header>
    <div className="jira-column"><div className="jira-column-title">TO DO <span>{stories.length}</span></div>
      {stories.map((story, index) => {
        const ticket = tickets?.[index];
        const url = safeJiraUrl(ticket?.url);
        const body = <><span className="jira-summary">{ticket?.fields?.summary ?? story.title}</span><span className="jira-label">discovery-agent</span><span className="jira-meta"><span className="jira-type" aria-hidden="true">▮</span><span className={`jira-key ${ticket ? "ready" : ""}`}>{ticket ? (ticket.dry_run ? "Preview" : ticket.key) : live ? "Creating…" : "Preparing…"}</span>{ticket && <span className="jira-check" aria-hidden="true">✓</span>}</span></>;
        const style = { animationDelay: `${index * 90}ms` };
        return url ? <a key={story.id} href={url} target="_blank" rel="noreferrer" className="jira-card" style={style}>{body}</a> : <div key={story.id} className={`jira-card ${ticket ? "" : "pending"}`} style={style}>{body}</div>;
      })}
    </div>
  </section>;
}
