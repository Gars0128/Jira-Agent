// PostToolUse: lint only the file that was just edited. Exit 2 shows the errors to Claude.
import { spawnSync } from "node:child_process";
import { relative, resolve } from "node:path";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw || "{}");
const file = input.tool_input?.file_path ?? input.tool_response?.filePath;
const root = process.env.CLAUDE_PROJECT_DIR ?? process.cwd();
if (!file) process.exit(0);

const path = relative(root, resolve(root, file)).replaceAll("\\", "/");
const api = resolve(root, "apps/api");
const web = resolve(root, "apps/web");
let command;
// Ruff runs from apps/api, like CI, so evals/ also gets the project's rule set.
if (/\.py$/.test(path) && /^(apps\/api|evals)\//.test(path)) command = ["uv", ["run", "ruff", "check", relative(api, resolve(root, path))], api];
else if (/\.(ts|tsx|mjs)$/.test(path) && path.startsWith("apps/web/")) command = ["npx", ["--no-install", "eslint", "--max-warnings=0", relative(web, resolve(root, path))], web];
if (!command) process.exit(0);

const [bin, args, cwd] = command;
// Windows needs a shell for npx/uv; quote only the arguments (paths have spaces, a quoted npx breaks).
const result = spawnSync([bin, ...args.map((part) => `"${part}"`)].join(" "), { cwd, encoding: "utf8", shell: true });
if (result.status !== 0) {
  process.stderr.write(`${bin} ${args.join(" ")} failed for ${path}:\n${result.stdout}${result.stderr}`);
  process.exit(2);
}
