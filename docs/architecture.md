# Architecture

## What are the moving pieces, and how do they talk to each other?

There are three main pieces:

**The Django app** — this is the whole backend. It handles incoming requests, runs business logic, talks to the database, and sends back rendered HTML pages. There is no separate API and no JavaScript framework. Everything is server-rendered.

**The SQLite database** — stores all the data. In development it's a single file (`db.sqlite3`) sitting in the project root. On Railway (production), it's swapped for a Postgres database via the `DATABASE_URL` environment variable.

**The browser** — the user's browser makes HTTP requests (GET to load a page, POST to submit a form) and receives HTML back. There are no background WebSocket connections, no AJAX calls, no client-side state. A form submission is a full page reload.

They talk to each other in a straight line: browser → Django → database → Django → browser. Nothing else is in the chain.

## Where does each piece run?

**Locally:**
- Django dev server runs on your machine, listening on port 8000
- SQLite is a file on disk (`db.sqlite3`) in the project root

**In production (Railway):**
- Django app runs as a single web process on Railway
- Database is Railway's managed Postgres
- Static files are served by WhiteNoise (Django serves its own static files — no separate CDN or web server)

## What is the request path for one representative user action, end to end?

Let's use "change a task's status from In Progress to In Review."

1. The user is on the task detail page and clicks the "Move to In Review" button.
2. The browser sends a `POST` to `/tasks/42/status/`.
3. Django matches that URL to `TaskStatusChangeView`.
4. `LoginRequiredMixin` checks the user is logged in. `ProjectAccessMixin` checks they're a manager or member of the project this task belongs to. If either check fails, the request stops here with a redirect or 403.
5. The view reads `new_status` from the POST data and calls `attempt_transition(task, "in_review", actor=request.user)`.
6. `attempt_transition` checks the move is in the allowed set (`in_progress → in_review` is allowed). It updates `task.status`, saves the task, and writes a `HistoryEntry` row recording the change.
7. The view adds a success message and redirects back to the task detail page.
8. The browser follows the redirect with a GET. Django renders the task detail page with the updated status and the new history entry visible in the timeline.
9. The browser displays the page.

The whole thing is synchronous and stateless from the server's perspective. No background jobs, no queues.

## What did you decide not to build, and why?

**No REST API.** The requirement was a working web app, not an API. Server-rendered HTML is simpler to build, simpler to deploy, and simpler to test when you don't have a separate frontend. Adding an API later is straightforward because the business logic already lives in `services.py`, `transitions.py`, and `audit.py` — those are not tied to the HTML layer.

**No charting library for the dashboard.** The 8-week completions chart is drawn directly on an HTML `<canvas>` element using a small inline script. No Chart.js, no D3. The data is simple enough (8 bars, one number each) that pulling in an external library would be more complexity than it saves.

**No real-time updates.** If two people have the same task open, one person's changes don't appear live for the other. A full page refresh shows the latest state. WebSockets or polling would add significant complexity for a feature that was not in the requirements.

**No file attachments.** The schema has no attachment model and the UI has no upload flow. It was not in the spec.

**No email notifications.** When a task is assigned or a due date changes, no email goes out. The alert system covers overdue tasks within the app itself, but nothing reaches outside it.

**No pagination on most lists.** Task list has pagination (25 per page). Project list and membership list do not — the assumption is that the number of projects and members per project stays manageable. If the app grew, those would need pagination too.
