import assert from "node:assert/strict";
import test from "node:test";
import { demoTarget, requireDryRun } from "./demo-safety.mjs";

test("capture refuses remote targets and credential-bearing URLs", () => {
  assert.equal(demoTarget("http://127.0.0.1:3001"), "http://127.0.0.1:3001");
  for (const unsafe of ["https://app.example", "http://localhost.attacker.test", "http://secret@localhost:3000", "file:///etc/passwd"]) assert.throws(() => demoTarget(unsafe));
});

test("capture fails closed before approval without explicit server dry-run mode", () => {
  assert.doesNotThrow(() => requireDryRun({ jira_dry_run: true }));
  for (const unsafe of [null, {}, { public_demo: true }, { jira_dry_run: false }, { jira_dry_run: "true" }]) assert.throws(() => requireDryRun(unsafe));
});
