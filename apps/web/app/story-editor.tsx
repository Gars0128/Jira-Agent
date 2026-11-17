import type { Story } from "../lib/types";

// Requirement links are shown, not edited: they come from the agent and the server validates them.
export function StoryEditor({ story, basedOn, editable, onChange }: { story: Story; basedOn: string[]; editable: boolean; onChange: (story: Story) => void }) {
  const update = (key: keyof Story, value: string | string[]) => onChange({ ...story, [key]: value });
  const field = (key: "title" | "as_a" | "i_want" | "so_that", label: string, rows = 1) => <label className="editor-field">
    <span>{label}</span>
    {rows === 1 ? <input value={story[key]} disabled={!editable} onChange={(event) => update(key, event.target.value)} />
      : <textarea rows={rows} value={story[key]} disabled={!editable} onChange={(event) => update(key, event.target.value)} />}
  </label>;
  return <div className="story-editor">
    {field("title", "Title")}
    {field("as_a", "As a")}
    {field("i_want", "I want", 2)}
    {field("so_that", "So that", 2)}
    <label className="editor-field"><span>Acceptance criteria <small>one per line</small></span>
      <textarea rows={Math.max(3, story.acceptance_criteria.length * 2)} value={story.acceptance_criteria.join("\n")} disabled={!editable} onChange={(event) => update("acceptance_criteria", event.target.value.split("\n"))} />
    </label>
    {!!basedOn.length && <div className="editor-field"><span>Based on what the client said</span><ul className="based-on">{basedOn.map((text) => <li key={text}>{text}</li>)}</ul></div>}
  </div>;
}
