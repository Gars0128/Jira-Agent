import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdir, unlink } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { demoTarget, requireDryRun } from "./demo-safety.mjs";

const [baseUrl, runId] = process.argv.slice(2);
if (!baseUrl || !runId) throw new Error("Usage: node scripts/capture-demo.mjs <web-url> <existing-run-id>");
const origin = demoTarget(baseUrl);
const configuration = await fetch(`${origin}/api/capabilities`);
if (!configuration.ok) throw new Error("Cannot verify the server's Jira mode; capture refused");
requireDryRun(await configuration.json());
const output = fileURLToPath(new URL("../../../docs/demo/", import.meta.url));
await mkdir(output, { recursive: true });
const frames = [];
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 1080 }, reducedMotion: "reduce" });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`${origin}/?run=${encodeURIComponent(runId)}`);
  await page.getByText(/^(Your review is ready|Completed)$/).waitFor();
  const screenshot = async (name) => {
    const path = `${output}${name}.png`;
    await page.evaluate(() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); });
    await page.screenshot({ path });
    frames.push(path);
  };
  await screenshot("01-workspace");
  const conflict = page.getByRole("button").filter({ has: page.locator(".badge-conflict") }).first();
  if (await conflict.count()) await conflict.click();
  await page.locator("#results").scrollIntoViewIfNeeded();
  await screenshot("02-evidence");
  await page.getByRole("tab", { name: /User stories/ }).click();
  const title = page.getByLabel("Title", { exact: true }).first();
  await title.waitFor();
  const canApprove = await title.isEnabled();
  if (canApprove) {
    const current = await page.request.get(`${origin}/api/capabilities`);
    assert.equal(current.ok(), true, "Cannot recheck Jira mode before approval");
    requireDryRun(await current.json());
    const reviewedTitle = `${(await title.inputValue()).replace(/ \(reviewed\)$/, "")} (reviewed)`;
    await title.fill(reviewedTitle);
    await page.locator("#results").scrollIntoViewIfNeeded();
    await screenshot("03-human-review");
    const responsePromise = page.waitForResponse((response) => response.url().endsWith("/approve") && response.request().method() === "POST");
    await page.getByRole("button", { name: "Approve & preview" }).click();
    const response = await responsePromise;
    const result = await response.json();
    assert.equal(response.status(), 200, JSON.stringify(result));
    assert.equal(result.status, "done");
    assert.ok(result.tickets.every((ticket) => ticket.dry_run === true), "Demo capture requires dry-run tickets");
    assert.equal(result.stories[0].title, reviewedTitle);
  } else {
    await screenshot("03-human-review");
    await page.getByRole("tab", { name: /Jira preview/ }).click();
  }
  await page.getByText("Reviewed. Approved. Ready.", { exact: true }).waitFor();
  await page.locator("#results").scrollIntoViewIfNeeded();
  await screenshot("04-jira-preview");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${output}desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.screenshot({ path: `${output}mobile.png`, fullPage: true });
  assert.deepEqual(errors, []);
} finally {
  await browser.close();
}

execFileSync("python", ["-c", `
import sys
from PIL import Image
frames = []
for path in sys.argv[2:]:
    image = Image.open(path).convert('RGB')
    image.thumbnail((960, 638), Image.Resampling.LANCZOS)
    frames.append(image.quantize(colors=128))
frames[0].save(sys.argv[1], save_all=True, append_images=frames[1:], duration=[1800, 2600, 2400, 2600], loop=0, optimize=True)
`, `${output}demo.gif`, ...frames], { stdio: "inherit" });
for (const path of frames) await unlink(path);
console.log(`Captured ${output}demo.gif, desktop.png, mobile.png`);
