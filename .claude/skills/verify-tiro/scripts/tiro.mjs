#!/usr/bin/env node
// Drive Tiro's web UI like a user and keep the evidence.
//   node .claude/skills/verify-tiro/scripts/tiro.mjs start [--port 3107]
//   node .claude/skills/verify-tiro/scripts/tiro.mjs doctor
//   node .claude/skills/verify-tiro/scripts/tiro.mjs journey <analyze-call|review-evidence|approve-preview|accessibility|all>
//   node .claude/skills/verify-tiro/scripts/tiro.mjs stop
// State lives in .verify/ at the repo root (git-ignored). Evidence stays after stop.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const web = join(root, "apps/web");
const state = join(root, ".verify");
const serverFile = join(state, "server.json");
const require = createRequire(join(web, "package.json"));
const [command, arg] = process.argv.slice(2);
const flag = (name, fallback) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : fallback; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const server = () => (existsSync(serverFile) ? JSON.parse(readFileSync(serverFile, "utf8")) : null);
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch { return false; } };

async function capabilities(url) {
  try { const r = await fetch(`${url}/api/capabilities`); return r.ok ? await r.json() : null; } catch { return null; }
}

async function start() {
  const port = Number(flag("--port", "3107"));
  const url = `http://localhost:${port}`; // not 127.0.0.1: Next dev blocks its client scripts for that origin
  if (server() && alive(server().pid)) throw new Error(`Already running (pid ${server().pid}); run stop first`);
  if (await capabilities(url)) throw new Error(`Port ${port} already answers and was not started by this skill; pick --port`);
  mkdirSync(state, { recursive: true });
  const log = openSync(join(state, "server.log"), "w");
  // One command string: Windows needs a shell for npx, and the port is a number we built.
  const child = spawn(`npx --no-install next dev -p ${port}`, {
    cwd: web, env: { ...process.env, DEMO_REPLAY: "true" }, detached: true, shell: process.platform === "win32", stdio: ["ignore", log, log],
  });
  child.unref();
  const commit = spawnSync("git", ["rev-parse", "--short", "HEAD"], { cwd: root, encoding: "utf8" }).stdout.trim();
  writeFileSync(serverFile, JSON.stringify({ pid: child.pid, port, url, commit, startedAt: new Date().toISOString() }, null, 2));
  for (let i = 0; i < 90; i++) {
    if ((await capabilities(url))?.replay === true) { console.log(`ready: ${url} (pid ${child.pid}, commit ${commit})`); return; }
    await sleep(1000);
  }
  throw new Error(`Not ready after 90 s; see ${join(state, "server.log")}`);
}

async function doctor() {
  const s = server();
  const checks = [];
  const add = (name, ok, detail = "") => checks.push({ name, ok, detail });
  add("server.json exists (started by this skill)", !!s);
  if (s) {
    add("process alive", alive(s.pid), `pid ${s.pid}`);
    const caps = await capabilities(s.url);
    add("replay mode", caps?.replay === true, JSON.stringify(caps));
    add("Jira dry-run", caps?.jira_dry_run === true);
    const head = spawnSync("git", ["rev-parse", "--short", "HEAD"], { cwd: root, encoding: "utf8" }).stdout.trim();
    add("same commit as at start", head === s.commit, `${s.commit} -> ${head}`);
    if (caps) {
      const { chromium } = require("@playwright/test");
      const browser = await chromium.launch();
      const page = await browser.newPage();
      await page.goto(s.url);
      const hydrated = await page.waitForFunction(() => !document.querySelector(".run-button")?.hasAttribute("disabled"), null, { timeout: 30000 }).then(() => true, () => false);
      add("page hydrated (Run discovery enabled)", hydrated);
      await browser.close();
    }
  }
  for (const c of checks) console.log(`${c.ok ? "ok  " : "FAIL"} ${c.name}${c.detail ? `  (${c.detail})` : ""}`);
  if (checks.some((c) => !c.ok)) process.exit(1);
}

function stop() {
  const s = server();
  if (!s) { console.log("nothing to stop"); return; }
  if (alive(s.pid)) {
    if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(s.pid), "/T", "/F"], { stdio: "ignore" });
    else process.kill(-s.pid, "SIGTERM");
  }
  rmSync(serverFile);
  console.log(`stopped pid ${s.pid}; evidence kept in ${join(state, "evidence")}`);
}

// --- journeys -------------------------------------------------------------
const journeys = {
  // Pick a recorded call, run it, watch progress, land on the review.
  async "analyze-call"(t) {
    const { page } = t;
    await t.open();
    t.check("problem statement visible", await page.locator(".page-heading .problem").isVisible());
    t.check("replay transcript is read-only", (await page.locator("#transcript").getAttribute("readonly")) !== null);
    t.check("no 'Write your own' in replay", (await page.locator("option", { hasText: "Write your own" }).count()) === 0);
    await page.getByRole("combobox", { name: "Conversation", exact: true }).selectOption({ label: "01 Exports" });
    await t.shot("1-before-run");
    const run = page.getByRole("button", { name: /Run discovery/ });
    const box = await run.boundingBox();
    t.check("Run discovery on first screen", !!box && box.y + box.height <= page.viewportSize().height);
    await run.click();
    await page.getByRole("button", { name: /Analyzing conversation/ }).waitFor();
    await t.shot("2-running");
    t.check("focus moved to results heading", await page.evaluate(() => document.activeElement?.id === "results-heading"));
    await page.getByText("Your review is ready", { exact: true }).waitFor({ timeout: 30000 });
    const heading = await page.locator("#results-heading").innerText();
    t.check("review heading counts tickets", /\d+ tickets? from this call/.test(heading), heading);
    for (const column of ["To build", "Needs decision", "Ask the client"]) t.check(`column '${column}' has a card`, (await page.getByRole("region", { name: column }).getByRole("button").count()) > 0);
    await t.shot("3-review");
    await t.aria("review");
  },
  // A ticket explains itself: quote, speaker, reason, spec section; a story can be edited.
  async "review-evidence"(t) {
    const { page } = t;
    await journeys["analyze-call"].reach(t);
    await page.getByRole("region", { name: "Needs decision" }).getByRole("button").first().click();
    const dialog = page.getByRole("dialog");
    await dialog.waitFor();
    const text = await dialog.innerText();
    t.check("dialog shows a quote", /“.+”/.test(text));
    t.check("dialog shows the speaker", text.includes("—"));
    t.check("dialog explains why", text.includes("Why"));
    t.check("dialog names the spec section", text.includes("From the spec:"));
    await t.shot("1-decision-dialog");
    await page.keyboard.press("Escape");
    t.check("Escape closes the dialog", !(await dialog.isVisible()));
    await page.getByRole("region", { name: "To build" }).getByRole("button").first().click();
    const title = page.getByLabel("Title", { exact: true }).first();
    await title.fill("Show monthly reservation counts in the report");
    await page.getByRole("button", { name: "Save", exact: true }).click();
    const card = await page.getByRole("region", { name: "To build" }).getByRole("button").first().innerText();
    t.check("edited story title shows on the card", card.includes("Show monthly reservation counts in the report"));
    await t.shot("2-story-edited");
  },
  // Approval creates a preview, keeps the edit, and sends nothing off this machine.
  async "approve-preview"(t) {
    const { page } = t;
    await journeys["review-evidence"].run(t);
    const create = page.locator(".approval-bar").getByRole("button");
    t.check("approve button says preview", /\(preview\)/.test(await create.innerText()));
    t.check("approve bar in view during review", await create.evaluate((e) => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }));
    await create.click();
    await page.getByRole("heading", { name: "Done" }).waitFor({ timeout: 30000 });
    const results = await page.locator("#results").innerText();
    t.check("preview wording", results.includes("Nothing was sent."));
    t.check("edited title survived approval", results.includes("Show monthly reservation counts in the report"));
    t.check("every card marked Preview", (await page.locator(".jira-meta").allInnerTexts()).every((m) => m.includes("Preview")));
    t.check("focus on Done", await page.evaluate(() => document.activeElement?.textContent === "Done"));
    const outside = t.requests.filter((u) => !/^(http:\/\/localhost|data:|blob:)/.test(u));
    t.check("no request left localhost (nothing sent to Jira)", outside.length === 0, outside.slice(0, 3).join(", "));
    await t.shot("1-done");
    await t.aria("done");
  },
  // WCAG 2.2 AA, focus, reduced motion and small screens.
  async accessibility(t) {
    const { page } = t;
    await journeys["analyze-call"].reach(t);
    await page.addScriptTag({ path: require.resolve("axe-core/axe.min.js") });
    const axe = await page.evaluate(() => window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"] }));
    t.write("axe-review.json", axe.violations);
    t.check("axe WCAG 2.2 AA on review", axe.violations.length === 0, axe.violations.map((v) => `${v.id}x${v.nodes.length}`).join(", "));
    const mobile = await t.browser.newPage({ viewport: { width: 390, height: 844 } });
    await mobile.goto(t.url);
    await mobile.getByRole("button", { name: /Run discovery/ }).waitFor();
    t.check("mobile: no horizontal scroll", !(await mobile.evaluate(() => document.documentElement.scrollWidth > innerWidth)));
    await mobile.screenshot({ path: join(t.dir, "1-mobile-start.png") });
    const calm = await t.browser.newContext({ reducedMotion: "reduce" });
    const still = await calm.newPage();
    await still.goto(t.url);
    await still.getByRole("button", { name: /Run discovery/ }).waitFor();
    t.check("reduced motion: nothing animates", await still.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length === 0));
  },
};
// Shared entry: reach the review state without re-checking analyze-call.
journeys["analyze-call"].reach = async (t) => {
  await t.open();
  await t.page.getByRole("button", { name: /Run discovery/ }).click();
  await t.page.getByText("Your review is ready", { exact: true }).waitFor({ timeout: 30000 });
};
journeys["review-evidence"].run = (t) => journeys["review-evidence"](t);

async function journey(name) {
  const s = server();
  if (!s || !(await capabilities(s.url))) throw new Error("No running instance from this skill; run start, then doctor");
  const names = name === "all" ? Object.keys(journeys) : [name];
  if (!names.every((n) => journeys[n])) throw new Error(`Unknown journey; use one of: ${Object.keys(journeys).join(", ")}, all`);
  const { chromium } = require("@playwright/test");
  let failed = 0;
  for (const n of names) {
    const dir = join(state, "evidence", `${new Date().toISOString().replace(/[:.]/g, "-")}-${n}`);
    mkdirSync(dir, { recursive: true });
    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const requests = [];
    const errors = [];
    page.on("request", (r) => requests.push(r.url()));
    page.on("pageerror", (e) => errors.push(e.message));
    const checks = [];
    const t = {
      page, browser, dir, requests, url: s.url,
      open: async () => { await page.goto(s.url); await page.waitForFunction(() => !document.querySelector(".run-button")?.hasAttribute("disabled"), null, { timeout: 30000 }); await page.waitForTimeout(700); },
      check: (what, ok, detail = "") => checks.push({ what, ok: !!ok, detail }),
      shot: (label) => page.screenshot({ path: join(dir, `${label}.png`) }),
      aria: async (label) => writeFileSync(join(dir, `${label}.aria.yml`), await page.locator("body").ariaSnapshot()),
      write: (file, data) => writeFileSync(join(dir, file), JSON.stringify(data, null, 2)),
    };
    try { await journeys[n](t); } catch (e) { checks.push({ what: "journey completed", ok: false, detail: e.message.split("\n")[0] }); await page.screenshot({ path: join(dir, "failure.png") }).catch(() => {}); }
    t.check("no page errors", errors.length === 0, errors.slice(0, 2).join("; "));
    writeFileSync(join(dir, "result.json"), JSON.stringify({ journey: n, url: s.url, commit: s.commit, checks, requests: [...new Set(requests.map((u) => new URL(u).origin))] }, null, 2));
    await browser.close();
    console.log(`\n# ${n}  ->  ${dir}`);
    for (const c of checks) console.log(`${c.ok ? "PASS" : "FAIL"}  ${c.what}${c.detail ? `  (${c.detail})` : ""}`);
    failed += checks.filter((c) => !c.ok).length;
  }
  if (failed) { console.log(`\n${failed} check(s) failed`); process.exit(1); }
}

const commands = { start, doctor, stop, journey: () => journey(arg) };
if (!commands[command]) { console.error("usage: tiro.mjs start [--port N] | doctor | journey <name|all> | stop"); process.exit(2); }
await commands[command]();
