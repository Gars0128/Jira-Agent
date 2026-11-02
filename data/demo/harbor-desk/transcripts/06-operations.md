# Harbor Desk discovery 06 — Support handoff

Mira (analyst): This is our last review before the draft. How did the weekend equipment fair go?
Eli (administrator): Quietly, fortunately. It reminded us that volunteers need to know whether the portal is unavailable without asking an administrator.
Mira (analyst): We currently have an internal health endpoint but no public status page.
Eli (administrator): Add a public read-only status page that shows whether the reservation service is available.
Mira (analyst): Should that page expose bookings or member names?
Eli (administrator): No. Show service availability only, without reservation data, member details or an action to change anything. I initially asked for recent error details, but leave those private.
Nora (cooperative lead): That page is different from a public reservation link. We still need the private-access decision from the earlier call.
Mira (analyst): Yes, the baseline allows a generic anonymous page, so a service-only status page is a new feature, not a change to reservation permissions. What retry behavior should email use?
Eli (administrator): Retry outbound email on 429 or 5xx at most three times after the initial attempt, with exponential backoff.
Mira (analyst): That matches the approved behavior. Any operational constraints we should add?
Nora (cooperative lead): Do not schedule database schema migrations on Saturdays or Sundays.
Mira (analyst): That is new; the baseline has no maintenance schedule. Which timezone should determine the day?
Nora (cooperative lead): Use the cooperative's configured local timezone. Emergency work needs its own decision; do not silently add an emergency bypass here.
Eli (administrator): We should monitor everything too.
Mira (analyst): Which events, thresholds, and who receives alerts? A status page does not define those choices.
Eli (administrator): I do not have that list. Capture the question rather than deploying an alert for every log line.
Mira (analyst): Good. I will return a draft with traceable requirements, not create tasks automatically. You can edit the story and acceptance criteria before approving anything.
