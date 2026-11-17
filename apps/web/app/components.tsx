import { safeJiraUrl, ticketColumns } from "../lib/presentation";
import type { Story, Ticket, TicketKind } from "../lib/types";

export function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <span aria-hidden="true">{diagonal ? "↗" : "→"}</span>;
}

export type BoardCard = {
  kind: TicketKind;
  title: string;
  quote?: string;
  speaker?: string;
  why?: string | null;
  specs: string[];
  story?: Story;
  ticket?: Ticket;
};

// Cards look like Jira and only open details; editing lives in a separate dialog.
export function TicketBoard({ cards, creating, live, onOpen }: { cards: BoardCard[]; creating: boolean; live: boolean; onOpen: (index: number) => void }) {
  const done = cards.some((card) => card.ticket);
  return <section className="ticket-board" aria-label="Jira board">
    <header><strong>Jira board</strong><span><i />{done ? (live ? "Created in Jira" : "Preview · nothing was sent") : creating ? "Sending…" : "Draft · click a ticket to open it"}</span></header>
    <div className="ticket-columns">{ticketColumns.map(([kind, title]) => {
      const column = cards.map((card, index) => ({ card, index })).filter(({ card }) => card.kind === kind);
      if (!column.length) return null;
      return <section key={kind} className="ticket-column" aria-label={title}>
        <h3>{title} <span>{column.length}</span></h3>
        {column.map(({ card, index }) => {
          const url = safeJiraUrl(card.ticket?.url);
          const key = card.ticket ? (card.ticket.dry_run ? "Preview" : card.ticket.key) : creating ? "Sending…" : "Draft";
          return <div key={index} className="jira-card">
            <button type="button" onClick={() => onOpen(index)}>
              <span className="jira-summary">{card.title}</span>
              <span className="jira-label">discovery-agent</span>
              <span className="jira-meta"><span className={`issue-type kind-${kind}`} aria-hidden="true" />{key}{card.ticket && <span className="jira-check" aria-label="sent">✓</span>}</span>
            </button>
            {url && <a href={url} target="_blank" rel="noreferrer">Open in Jira <Arrow diagonal /></a>}
          </div>;
        })}
      </section>;
    })}</div>
  </section>;
}
