export function demoTarget(value) {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol) || !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) || url.username || url.password) {
    throw new Error("Demo capture is restricted to a local web server without URL credentials");
  }
  return url.origin;
}

export function requireDryRun(capabilities) {
  if (capabilities?.jira_dry_run !== true) throw new Error("Demo capture refuses approval unless the server confirms Jira dry-run mode");
}
