import type { Story } from "../lib/types";

// Requirement links are shown, not edited: they come from the agent and the server validates them.
export function StoryEditor({ story, number, basedOn, editable, onChange }: { story: Story; number: number; basedOn: string[]; editable: boolean; onChange: (story: Story) => void }) {
  const update = (key: keyof Story, value: string | string[]) => onChange({ ...story, [key]: value });
  return <article className="story-card">
    <div className="card-eyebrow"><span>Ticket {number}</span><span className="tag">User story</span></div>
    <label className="field-label" htmlFor={`${story.id}-title`}>Title</label>
    <input id={`${story.id}-title`} className="story-title" value={story.title} disabled={!editable} onChange={(event) => update("title", event.target.value)} />
    <div className="story-sentence">
      {([ ["as_a", "As a"], ["i_want", "I want"], ["so_that", "So that"] ] as const).map(([key, label]) => <label key={key}><span>{label}</span><textarea rows={2} value={story[key]} disabled={!editable} onChange={(event) => update(key, event.target.value)} /></label>)}
    </div>
    <label className="field-label" htmlFor={`${story.id}-criteria`}>Acceptance criteria <span>How to check it&rsquo;s done, one per line</span></label>
    <textarea id={`${story.id}-criteria`} rows={Math.max(3, story.acceptance_criteria.length * 2)} value={story.acceptance_criteria.join("\n")} disabled={!editable} onChange={(event) => update("acceptance_criteria", event.target.value.split("\n"))} />
    {!!basedOn.length && <><span className="field-label">Based on what the client said</span><ul className="based-on">{basedOn.map((text) => <li key={text}>{text}</li>)}</ul></>}
  </article>;
}
