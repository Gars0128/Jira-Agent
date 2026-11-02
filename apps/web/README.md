# Discovery web

Next.js App Router, React, strict TypeScript, and Tailwind. The browser talks to
`/api/*`; Next forwards those requests to the Python service. No provider or
database secrets belong in the web application.

Use Node.js 24 LTS. From `apps/web`:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open <http://localhost:3000>. Start the backend on port 8000 first. Set `API_URL`
in `.env.local` to use a different backend; set it before building on Vercel.
The Vercel project root is `apps/web`.

## Checks

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npx.cmd playwright install chromium
npm.cmd run test:e2e
npm.cmd run build
```

CI/Linux uses `npm` and `npx` without `.cmd`. Browser tests substitute the API:
they check rendering, evidence, story edits, approval, preview, and an unavailable
backend without calling an LLM or Jira. The main test also checks mobile overflow.

## Manual walkthrough

Select Harbor Desk and a conversation, run discovery, then inspect a requirement's
quote and specification context. Open User stories, edit the fields and acceptance
criteria, then approve. Public demo mode returns Jira previews. An existing run can
be reopened with `/?run=<run_id>`; the backend owns persisted state.

The web application uses SSE for progress and polling as a connection fallback.
Snapshot reads are serialized and cancelled when switching runs. `/capabilities`
provides the effective Jira mode; approval rechecks that mode before submitting.
Unsaved story edits stay in the current browser tab; refreshing reloads the last
server-side draft. Approval validates the edited payload again on the server.
