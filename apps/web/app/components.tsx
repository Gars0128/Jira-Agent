import { safeJiraUrl } from "../lib/presentation";
import type { Requirement, Run, Story, Ticket } from "../lib/types";

export function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <span aria-hidden="true">{diagonal ? "↗" : "→"}</span>;
}

export function EmptyState({ symbol, title, text, working = false }: { symbol: string; title: string; text: string; working?: boolean }) {
  return <div className={`empty-state ${working ? "working" : ""}`}><span className="empty-symbol" aria-hidden="true">{symbol}</span><h3>{title}</h3><p>{text}</p></div>;
}

export function Evidence({ requirement, run }: { requirement: Requirement; run: Run }) {
  const chunks = run.retrieved?.[requirement.id] ?? [];
  return <aside className="evidence-panel"><div className="eyebrow">EVIDENCE / {requirement.id}</div><h3>Why this classification?</h3><p className="evidence-note">{requirement.note ?? "No classification rationale was provided."}</p><div className="evidence-source"><span className="field-label">Original client quote</span><blockquote><mark>{requirement.quote}</mark></blockquote><span className="muted">— {requirement.speaker}</span></div><h4>Specification context <span>{chunks.length} excerpts</span></h4>{chunks.map((chunk) => <details key={chunk.id} open={requirement.spec_refs.includes(chunk.id)}><summary><span>{chunk.id}</span>{requirement.spec_refs.includes(chunk.id) && <span className="cited">CITED</span>}</summary><p>{chunk.text}</p><small>Cosine distance {chunk.distance.toFixed(3)}</small></details>)}{!chunks.length && <p className="muted">No retrieved excerpts are available.</p>}</aside>;
}

export function TicketCard({ ticket, story }: { ticket: Ticket; story?: Story }) {
  const url = safeJiraUrl(ticket.url);
  return <article className="ticket-card">
    <header><span className="ticket-type" aria-hidden="true">▮</span><span className="ticket-key">{ticket.key ?? "DRY RUN"}</span>{ticket.dry_run ? <span className="tag">PREVIEW</span> : <span className="tag tag-live">{ticket.reused ? "ALREADY IN JIRA" : "CREATED"}</span>}{url && <a href={url} target="_blank" rel="noreferrer">Open in Jira <Arrow diagonal /></a>}</header>
    <h3>{ticket.fields?.summary ?? story?.title ?? "Approved story"}</h3>
    {story && <><p className="ticket-sentence">As a <strong>{story.as_a}</strong>, I want <strong>{story.i_want}</strong>, so that <strong>{story.so_that}</strong>.</p>
      <span className="field-label">Acceptance criteria</span><ul>{story.acceptance_criteria.map((item, index) => <li key={index}>{item}</li>)}</ul>
      <footer>Linked requirements · {story.requirement_ids.join(", ")}</footer></>}
    {ticket.fields && <details><summary>Jira payload</summary><pre>{JSON.stringify(ticket.fields, null, 2)}</pre></details>}
  </article>;
}

export function JiraBoard({ stories, tickets, live }: { stories: Story[]; tickets?: Ticket[]; live: boolean }) {
  if (!stories.length || (tickets && !tickets.length)) return null;
  const status = tickets ? (live ? "Created in Jira" : "Dry run · nothing was sent") : (live ? "Creating tickets in Jira…" : "Building the Jira preview…");
  return <section className="jira-board" aria-label="Jira board" aria-busy={!tickets}>
    <header><strong>Jira board</strong><span className={tickets ? "jira-status-done" : "jira-status-busy"}><i />{status}</span></header>
    <div className="jira-column"><div className="jira-column-title">TO DO <span>{stories.length}</span></div>
      {stories.map((story, index) => {
        const ticket = tickets?.[index];
        const url = safeJiraUrl(ticket?.url);
        const body = <><span className="jira-summary">{ticket?.fields?.summary ?? story.title}</span><span className="jira-label">discovery-agent</span><span className="jira-meta"><span className="jira-type" aria-hidden="true">▮</span><span className={`jira-key ${ticket ? "ready" : ""}`}>{ticket ? ticket.key ?? "PREVIEW" : "Creating…"}</span>{ticket && <span className="jira-check" aria-hidden="true">✓</span>}</span></>;
        const style = { animationDelay: `${index * 90}ms` };
        return url ? <a key={story.id} href={url} target="_blank" rel="noreferrer" className="jira-card" style={style}>{body}</a> : <div key={story.id} className={`jira-card ${ticket ? "" : "pending"}`} style={style}>{body}</div>;
      })}
    </div>
  </section>;
}
