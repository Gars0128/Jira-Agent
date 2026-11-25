// Append one JSON line per blocked hook run so we can count what the hooks actually catch.
import { appendFileSync } from "node:fs";
import { resolve } from "node:path";

export function recordBlocks(root, hook, entries) {
  const ts = new Date().toISOString();
  const lines = entries.map((entry) => JSON.stringify({ ts, hook, ...entry })).join("\n");
  appendFileSync(resolve(root, ".claude/metrics.jsonl"), `${lines}\n`);
}

// Rule IDs from ruff ("E402 Message") and ESLint stylish ("  1:7  error  Message  rule-id") output.
export function ruleIds(output) {
  const ruff = [...output.matchAll(/^([A-Z]+\d+) /gm)].map((match) => match[1]);
  const eslint = [...output.matchAll(/^\s+\d+:\d+\s+(?:error|warning)\s.*\s(\S+)$/gm)].map((match) => match[1]);
  const ids = [...new Set([...ruff, ...eslint])];
  return ids.length ? ids : ["unparsed"];
}
