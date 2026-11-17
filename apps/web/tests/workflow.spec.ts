import { expect, test } from "@playwright/test";
import type { Run } from "../lib/types";

const ready: Run = {
  run_id: "demo-run", status: "awaiting_review",
  requirements: [
    { id: "R1", text: "Add a monthly export count", type: "functional", priority: "must", quote: "Show the monthly export count.", speaker: "Maya", status: "new", spec_refs: ["HD-EXPORT"], note: "A count is outside the baseline." },
    { id: "R2", text: "Allow coordinator exports", type: "functional", priority: "should", quote: "Coordinators should export too.", speaker: "Maya", status: "conflict", spec_refs: ["HD-EXPORT"], note: "Exports are limited to administrators." },
  ],
  stories: [{ id: "S1", title: "View monthly export count", as_a: "administrator", i_want: "a monthly count", so_that: "I can monitor activity", acceptance_criteria: ["Given recorded exports, when I view the month, then I see the count."], requirement_ids: ["R1"], idempotency_key: "server-owned" }],
  questions: ["Should coordinator exports be approved as a policy change?"],
  retrieved: { R1: [{ id: "HD-EXPORT", text: "Only administrators may export reports.", distance: .2 }], R2: [{ id: "HD-EXPORT", text: "Only administrators may export reports.", distance: .2 }] },
  usage: { cost_usd: "0.0123" }, latency_ms: 8200, trace_url: null, tickets: [], error: null,
};

test("preset → evidence → edited story → approved Jira preview", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  let approved = false;
  let editedTitle = "";
  const tickets = [{ key: "DRY-1", dry_run: true, kind: "story" }, { key: "DRY-2", dry_run: true, kind: "decision", summary: "Decide: Allow coordinator exports" }];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/capabilities") return route.fulfill({ json: { public_demo: true, jira_dry_run: true, transcript_limit: 20000 } });
    if (path === "/api/projects") return route.fulfill({ json: { projects: [{ id: "harbor-desk", name: "Harbor Desk", spec: true, transcripts: [{ id: "01-exports", name: "01 · Exports", text: "Maya: Show the monthly export count. Coordinators should export too." }] }] } });
    if (path === "/api/runs" && route.request().method() === "POST") return route.fulfill({ json: { run_id: "demo-run" } });
    if (path.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: 'data: {"type":"awaiting_review"}\n\n' });
    if (path.endsWith("/approve")) {
      const payload = route.request().postDataJSON();
      editedTitle = payload.stories[0].title;
      approved = true;
      return route.fulfill({ json: { ...ready, status: "done", stories: payload.stories, tickets } });
    }
    return route.fulfill({ json: approved ? { ...ready, status: "done", tickets } : ready });
  });
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto("/");
  await expect(page.getByLabel("Transcript", { exact: true })).toHaveValue(/monthly export count/);
  await page.screenshot({ path: "test-results/studio-desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Run discovery" }).click();
  await expect(page.getByText("Your review is ready", { exact: true })).toBeVisible();
  // The conflict becomes a decision card that explains itself.
  await expect(page.getByRole("heading", { name: "2 tickets from this call" })).toBeVisible();
  await page.getByRole("region", { name: "Needs decision" }).getByRole("button", { name: /Decide: Allow coordinator exports/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Exports are limited to administrators.", { exact: true })).toBeVisible();
  await expect(dialog.getByText("From the spec: HD-EXPORT")).toBeVisible();
  await page.screenshot({ path: "test-results/evidence-desktop.png", fullPage: true });
  await dialog.getByRole("button", { name: "Close", exact: true }).first().click();
  await page.getByRole("region", { name: "To build" }).getByRole("button").first().click();
  await page.getByLabel("Title", { exact: true }).fill("Review the monthly export count");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "Create 2 tickets (preview)" }).click();
  await expect(page.getByRole("heading", { name: "Done" })).toBeVisible();
  expect(editedTitle).toBe("Review the monthly export count");
  await expect(page.getByRole("button", { name: new RegExp(editedTitle) })).toBeVisible();
  await expect(page.locator(".jira-meta", { hasText: "Preview" })).toHaveCount(2);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/studio-mobile.png", fullPage: true });
  expect(pageErrors).toEqual([]);
});

test("SSE and polling serialize reads and keep a review draft intact", async ({ page }) => {
  let reads = 0;
  let release: () => void = () => {};
  const firstSnapshot = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/projects") return route.fulfill({ json: { projects: [{ id: "harbor-desk", name: "Harbor Desk", spec: true, transcripts: [] }] } });
    if (path === "/api/capabilities") return route.fulfill({ json: { public_demo: true, jira_dry_run: true, transcript_limit: 20000 } });
    if (path.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: 'data: {"type":"node_started","node":"extract"}\n\n' });
    reads += 1;
    await firstSnapshot;
    return route.fulfill({ json: ready });
  });
  await page.goto("/?run=demo-run");
  await expect(page.getByText("RUNNING", { exact: true })).toBeVisible();
  expect(reads).toBe(1);
  await expect(page.getByRole("button", { name: /Analyzing conversation/ })).toBeDisabled();
  release();
  await expect(page.getByText("Your review is ready", { exact: true })).toBeVisible();
  const ticket = page.getByRole("region", { name: "To build" }).getByRole("button").first();
  await ticket.click();
  await page.getByLabel("Title", { exact: true }).fill("Keep this human edit");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await ticket.click();
  await expect(page.getByLabel("Title", { exact: true })).toHaveValue("Keep this human edit");
});

test("approval refuses a dry-run to live-mode change and preserves edits", async ({ page }) => {
  let modeChanged = false;
  let approvals = 0;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/projects") return route.fulfill({ json: { projects: [{ id: "harbor-desk", name: "Harbor Desk", spec: true, transcripts: [] }] } });
    if (path === "/api/capabilities") return route.fulfill({ json: { public_demo: !modeChanged, jira_dry_run: !modeChanged, transcript_limit: 20000 } });
    if (path.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: 'data: {"type":"awaiting_review"}\n\n' });
    if (path.endsWith("/approve")) { approvals += 1; return route.fulfill({ json: { ...ready, status: "done" } }); }
    return route.fulfill({ json: { ...ready, trace_url: "javascript:alert(1)" } });
  });
  await page.goto("/?run=demo-run");
  await expect(page.getByText("Your review is ready", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /LangSmith/ })).toHaveCount(0);
  const ticket = page.getByRole("region", { name: "To build" }).getByRole("button").first();
  await ticket.click();
  await page.getByLabel("Title", { exact: true }).fill("Unsaved review draft");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  modeChanged = true;
  await page.getByRole("button", { name: "Create 2 tickets (preview)" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Jira mode changed" })).toBeVisible();
  expect(approvals).toBe(0);
  await ticket.click();
  await expect(page.getByLabel("Title", { exact: true })).toHaveValue("Unsaved review draft");
  await expect(page.getByLabel("Title", { exact: true })).toBeEnabled();
});

test("backend outage is actionable and does not permit a run", async ({ page }) => {
  await page.route("**/api/projects", (route) => route.fulfill({ status: 503, json: { detail: "unavailable" } }));
  await page.goto("/");
  await expect(page.getByRole("alert").filter({ hasText: "Start the backend" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run discovery" })).toBeDisabled();
});

test("mode pill never claims live Jira before capabilities load; tickets show what they are based on", async ({ page }) => {
  let release: () => void = () => {};
  const capabilitiesReady = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/capabilities") { await capabilitiesReady; return route.fulfill({ json: { public_demo: false, jira_dry_run: false, transcript_limit: 20000 } }); }
    if (path === "/api/projects") return route.fulfill({ json: { projects: [{ id: "harbor-desk", name: "Harbor Desk", spec: true, transcripts: [] }] } });
    if (path.endsWith("/events")) return route.fulfill({ contentType: "text/event-stream", body: 'data: {"type":"awaiting_review"}\n\n' });
    return route.fulfill({ json: ready });
  });
  await page.goto("/?run=demo-run");
  await expect(page.getByText("Checking mode…")).toBeVisible();
  await expect(page.getByText("Live Jira", { exact: true })).toHaveCount(0);
  release();
  await expect(page.getByText("Live Jira", { exact: true })).toBeVisible();
  await page.getByRole("region", { name: "To build" }).getByRole("button").first().click();
  const basedOn = page.locator(".based-on");
  await expect(basedOn).toHaveText("Add a monthly export count");
  await expect(basedOn).not.toContainText("R1");
});
