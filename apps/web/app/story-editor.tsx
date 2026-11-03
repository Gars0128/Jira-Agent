import { useState } from "react";
import type { Story } from "../lib/types";

export function StoryEditor({ story, editable, onChange }: { story: Story; editable: boolean; onChange: (story: Story) => void }) {
  const update = (key: keyof Story, value: string | string[]) => onChange({ ...story, [key]: value });
  // Show raw text so a trailing comma survives; the parent gets parsed IDs.
  const [refs, setRefs] = useState(story.requirement_ids.join(", "));
  return <article className="story-card">
    <div className="card-eyebrow"><span>{story.id}</span><span className="tag">User story</span></div>
    <label className="field-label" htmlFor={`${story.id}-title`}>Title</label>
    <input id={`${story.id}-title`} className="story-title" value={story.title} disabled={!editable} onChange={(event) => update("title", event.target.value)} />
    <div className="story-sentence">
      {([ ["as_a", "As a"], ["i_want", "I want"], ["so_that", "So that"] ] as const).map(([key, label]) => <label key={key}><span>{label}</span><textarea rows={2} value={story[key]} disabled={!editable} onChange={(event) => update(key, event.target.value)} /></label>)}
    </div>
    <label className="field-label" htmlFor={`${story.id}-criteria`}>Acceptance criteria <span>One criterion per line</span></label>
    <textarea id={`${story.id}-criteria`} rows={Math.max(3, story.acceptance_criteria.length * 2)} value={story.acceptance_criteria.join("\n")} disabled={!editable} onChange={(event) => update("acceptance_criteria", event.target.value.split("\n"))} />
    <label className="field-label" htmlFor={`${story.id}-refs`}>Requirement links</label>
    <input id={`${story.id}-refs`} value={refs} disabled={!editable} onChange={(event) => { setRefs(event.target.value); update("requirement_ids", event.target.value.split(",").map((id) => id.trim()).filter(Boolean)); }} />
  </article>;
}
