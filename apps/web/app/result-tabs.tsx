import type { KeyboardEvent } from "react";

export type ResultTab = "requirements" | "stories" | "preview";

export function ResultTabs({ selected, onChange, counts }: {
  selected: ResultTab;
  onChange: (tab: ResultTab) => void;
  counts: [number, number, number];
}) {
  const tabs = [["requirements", "Requirements"], ["stories", "User stories"], ["preview", "Jira preview"]] as const;
  function navigate(event: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex(([id]) => id === selected);
    let next: number;
    switch (event.key) {
      case "ArrowRight": next = (index + 1) % tabs.length; break;
      case "ArrowLeft": next = (index + tabs.length - 1) % tabs.length; break;
      case "Home": next = 0; break;
      case "End": next = tabs.length - 1; break;
      default: return;
    }
    event.preventDefault();
    onChange(tabs[next][0]);
    event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=tab]")[next].focus();
  }
  return <div className="result-tabs" role="tablist" aria-label="Discovery results" onKeyDown={navigate}>
    {tabs.map(([id, label], index) => <button key={id} type="button" role="tab" id={`tab-${id}`} tabIndex={selected === id ? 0 : -1} aria-controls={`panel-${id}`} aria-selected={selected === id} onClick={() => onChange(id)}>{label}<span>{counts[index]}</span></button>)}
  </div>;
}
