// Stop: type-check and run the fast test suites when code changed. Exit 2 sends failures back.
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { recordBlocks } from "./metrics.mjs";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw || "{}");
// Claude is already fixing a failure from this hook; don't block the same stop twice.
if (input.stop_hook_active) process.exit(0);

const root = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
// Windows needs a shell for npx/npm/uv; quote only the arguments (paths have spaces, a quoted npx breaks).
const run = (bin, args, cwd) => spawnSync([bin, ...args.map((part) => `"${part}"`)].join(" "), { cwd: resolve(root, cwd), encoding: "utf8", shell: true });
const changed = run("git", ["status", "--porcelain", "--", "apps/api", "apps/web", "evals"], ".").stdout.trim();
if (!changed) process.exit(0);

const checks = [
  ["tsc --noEmit", "npx", ["--no-install", "tsc", "--noEmit"], "apps/web"],
  ["web unit tests", "npm", ["test", "--silent"], "apps/web"],
  ["pytest", "uv", ["run", "pytest", "-q"], "apps/api"],
];
const failed = checks.flatMap(([name, bin, args, cwd]) => {
  const result = run(bin, args, cwd);
  return result.status === 0 ? [] : [{ name, report: `## ${name} failed (${cwd})\n${`${result.stdout}${result.stderr}`.trim().split("\n").slice(-40).join("\n")}` }];
});
if (failed.length) {
  recordBlocks(root, "check-all", failed.map(({ name }) => ({ file: null, check: name })));
  process.stderr.write(`${failed.map(({ report }) => report).join("\n\n")}\n\nFix these before finishing.`);
  process.exit(2);
}
