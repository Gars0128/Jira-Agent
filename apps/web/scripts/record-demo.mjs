// Records the README demo against a replay-mode server (DEMO_REPLAY=true).
import { rename, rm } from "node:fs/promises";
import { chromium } from "@playwright/test";

const [baseUrl, output] = process.argv.slice(2);
if (!baseUrl || !output) throw new Error("Usage: node scripts/record-demo.mjs <replay-web-url> <output-dir>");
const capabilities = await (await fetch(`${baseUrl}/api/capabilities`)).json();
if (capabilities.replay !== true) throw new Error("Recording requires a replay-mode server");

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: `${output}/.video`, size: { width: 1280, height: 800 } } });
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);
await page.goto(baseUrl, { waitUntil: "networkidle" });
await page.getByLabel("Transcript", { exact: true }).waitFor(); await pause(1800);
await page.screenshot({ path: `${output}/tiro-studio.png` });
await page.getByRole("button", { name: /Run discovery/ }).click();
await page.getByText("Your review is ready", { exact: true }).waitFor({ timeout: 30000 }); await pause(1600);
const decision = page.getByRole("region", { name: "Needs decision" }).getByRole("button").first();
await decision.scrollIntoViewIfNeeded(); await pause(500); await decision.click(); await pause(2600);
await page.screenshot({ path: `${output}/tiro-evidence.png` });
await page.keyboard.press("Escape"); await pause(400);
await page.getByRole("region", { name: "To build" }).getByRole("button").first().click(); await pause(1200);
await page.getByLabel("Title", { exact: true }).first().click();
await page.keyboard.press("Control+A");
await page.keyboard.type("Show monthly reservation counts in the report", { delay: 45 }); await pause(900);
await page.getByRole("button", { name: "Save", exact: true }).click(); await pause(500);
const approve = page.locator(".approval-bar").getByRole("button");
await approve.scrollIntoViewIfNeeded(); await pause(500); await approve.click();
await page.getByRole("heading", { name: "Done" }).waitFor(); await page.locator(".ticket-board").scrollIntoViewIfNeeded(); await pause(2800);
await page.screenshot({ path: `${output}/tiro-jira.png` });
const video = page.video();
await context.close(); await browser.close();
await rename(await video.path(), `${output}/tiro-demo.webm`);
await rm(`${output}/.video`, { recursive: true, force: true });
console.log(`Recorded ${output}/tiro-demo.webm and screenshots`);
