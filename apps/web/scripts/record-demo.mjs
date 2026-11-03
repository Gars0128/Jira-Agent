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
const conflict = page.getByRole("button").filter({ has: page.locator(".badge-conflict") }).first();
await conflict.scrollIntoViewIfNeeded(); await pause(500); await conflict.click(); await pause(2600);
await page.screenshot({ path: `${output}/tiro-evidence.png` });
await page.getByRole("tab", { name: /User stories/ }).click(); await pause(1200);
await page.getByLabel("Title", { exact: true }).first().click();
await page.keyboard.press("Control+A");
await page.keyboard.type("Show monthly reservation counts in the report", { delay: 45 }); await pause(900);
const approve = page.getByRole("button", { name: /Approve & preview/ });
await approve.scrollIntoViewIfNeeded(); await pause(500); await approve.click();
await page.locator(".jira-board").waitFor(); await page.locator(".jira-board").scrollIntoViewIfNeeded(); await pause(800);
await page.getByText("Reviewed. Approved. Ready.", { exact: true }).waitFor(); await pause(2800);
await page.screenshot({ path: `${output}/tiro-jira.png` });
const video = page.video();
await context.close(); await browser.close();
await rename(await video.path(), `${output}/tiro-demo.webm`);
await rm(`${output}/.video`, { recursive: true, force: true });
console.log(`Recorded ${output}/tiro-demo.webm and screenshots`);
