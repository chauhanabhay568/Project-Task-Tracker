# Project & Task Tracker

A multi-project task tracking app, built with Django. Managers set up projects, decide who's on
each one, and see the whole portfolio at a glance. Staff see what's assigned to them across every
project and move it forward. Every status change, assignment, and comment is recorded on an
append-only timeline, so "what happened to this task" always has an answer.

**Live app:** https://project-task-tracker.up.railway.app
(Free-tier hosting — the first request after a quiet period can take up to ~30s to wake.)

## Features

- **Roles enforced server-side** — manager and member roles, with permission checks on every
  view, not just hidden UI.
- **Projects** — create, edit, archive, and restore. Archiving hides a project from default views
  without deleting its data.
- **Tasks with a real lifecycle** — Backlog → In Progress → In Review → Done, with Blocked/Unblock
  and reopen. Illegal transitions (e.g. Backlog → Done) are rejected server-side with an
  explanation; a task can't reach Done while an unfinished task blocks it.
- **Assignment** — any number of people per task, restricted to project members; removing someone
  from a project cascades to unassign them from that project's tasks.
- **Search, filter, sort, pagination** — all server-side, across every project the viewer can see.
- **Bulk actions** — select tasks from the list and apply a status change, assignee, or due date
  to all of them at once; the result reports per task what succeeded and what was rejected and why.
- **CSV export** of the currently filtered task list.
- **Dashboard** — open/overdue/due-this-week/completed-this-week counts, a breakdown by status and
  assignee, and an 8-week completions chart.
- **Immutable history** — every field change, assignment, and comment on a task, with who and
  when. Nothing in the timeline can be edited or deleted after the fact.
- **Overdue alerts** — a nav badge and alert list for tasks past due; dismissals are
  per-user and reappear automatically if the due date changes after dismissal.

## Stack

| Layer    | Choice                                 |
|----------|-----------------------------------------|
| Backend  | Django 4.2 (Python)                     |
| Frontend | Server-rendered Django templates        |
| Database | SQLite (local dev), PostgreSQL (prod)   |
| Hosting  | Railway                                 |

## Running it locally

```bash
# install dependencies (uses uv; swap for pip if you prefer)
uv sync

# apply migrations
python manage.py migrate

# load demo users, projects, and tasks (safe to re-run)
python manage.py seed

# run the dev server
python manage.py runserver
```

Then visit `http://127.0.0.1:8000/` and log in with one of the seeded accounts below.

### Demo credentials

| Role    | Email          | Password |
|---------|----------------|----------|
| Manager | alice@demo.com | demo1234 |
| Manager | bob@demo.com   | demo1234 |
| Member  | carol@demo.com | demo1234 |
| Member  | dave@demo.com  | demo1234 |
| Member  | eve@demo.com   | demo1234 |

### Environment variables

| Variable       | Purpose                                      | Default (local dev)        |
|----------------|-----------------------------------------------|-----------------------------|
| `SECRET_KEY`   | Django secret key                             | insecure dev key (not for prod) |
| `DEBUG`        | Debug mode                                    | `True`                      |
| `ALLOWED_HOSTS`| Comma-separated allowed hosts                 | `localhost,127.0.0.1`       |
| `DATABASE_URL` | Postgres connection string (used if set)      | unset → falls back to SQLite |

## Project docs

More detail on how this was built and why lives under [`docs/`](docs/):

- [`docs/architecture.md`](docs/architecture.md) — moving pieces and request flow
- [`docs/schema.md`](docs/schema.md) — database schema and design trade-offs
- [`docs/decisions.md`](docs/decisions.md) — key decisions and why
- [`docs/plan.md`](docs/plan.md) — how the work was sequenced
- [`docs/ai-prompts.md`](docs/ai-prompts.md) — AI usage log
- [`SUBMISSION.md`](SUBMISSION.md) — submission notes and goal checklist
