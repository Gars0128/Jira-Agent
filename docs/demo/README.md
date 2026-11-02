# Recorded local demonstration

`demo.gif`, `desktop.png`, and `mobile.png` show the real local Next.js UI using
the FastAPI/Neon workflow. The sequence opens an existing run, checks conflict
evidence, edits a user story, approves it, and displays a Jira dry-run preview.
These are browser captures, not generated mockups. Hosting is verified separately.

To recreate from `apps/web`, use an existing run awaiting review and public demo
mode. The script accepts local web servers only and requires `/capabilities` to
confirm effective `jira_dry_run: true` before it opens the browser and again before
approval. An unavailable or live-mode server is rejected. This script approves
that run; it does not start a new paid analysis.

```powershell
node scripts/capture-demo.mjs http://localhost:3000 <run-id>
```

Requirements: installed web development dependencies, Playwright Chromium, and
Python with Pillow. Intermediate capture frames are removed after GIF creation.
