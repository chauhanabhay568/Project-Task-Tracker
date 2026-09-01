# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use `uv` for environment management. Never activate the venv manually.

```bash
uv run python manage.py runserver        # dev server
uv run python manage.py migrate          # apply migrations
uv run python manage.py makemigrations tracker  # generate migrations after model changes
uv run python manage.py test tracker    # run all tests
uv run python manage.py test tracker.tests.TestClassName  # run one test class
uv run python manage.py shell           # Django shell
uv run python manage.py check           # validate settings/models without running
```

Adding a dependency: edit `pyproject.toml` then run `uv sync`.

## Project layout

```
config/          Django project package — settings, root urls, wsgi/asgi
tracker/         The one app — all models, views, urls, and business logic live here
docs/            Required submission docs (schema, decisions, architecture, plan, ai-prompts)
```

## Architecture

Standard Django monolith. One project (`config`), one app (`tracker`). No frontend framework — server-rendered templates (not yet built). Database is SQLite locally; psycopg2-binary is installed for Postgres in production.

`AUTH_USER_MODEL = 'tracker.User'` — the custom user model is `tracker.User` (extends `AbstractUser`, adds `role`). Always import `User` from `tracker.models`, never from `django.contrib.auth.models`.

## Key domain rules encoded in models

- **Task status flow:** `Backlog → In Progress → In Review → Done`. `Blocked` is reachable from `In Progress` or `In Review` only. When a task is blocked, its pre-block status is saved in `pre_blocked_status` and restored on unblock. The server must reject illegal transitions.
- **Blocker gate:** A task with any unfinished blocking task cannot move to `Done`. Server rejects the attempt.
- **TaskBlocker** is self-referential on `Task`. `task.blocked_by.all()` → tasks blocking it; `task.blocks.all()` → tasks it blocks.
- **Audit log:** All writes to `HistoryEntry` must go through `tracker.audit.log_change()`. Never write to `HistoryEntry` directly anywhere else.
- **Comments are append-only.** No edit or delete view should ever be built for `Comment`.
- **AlertDismissal** stores `due_date_at_dismissal` as a snapshot. If `task.due_date != dismissal.due_date_at_dismissal`, the alert reappears for that user.
- **ProjectMembership and TaskAssignment** are explicit join models (not `ManyToManyField`) because they carry timestamps. Removing a user from a project must also unassign them from that project's tasks.

## Roles and permissions

Two roles: `manager`, `member`. Enforcement is server-side (not just UI). Key distinctions:
- Managers: create and archive projects, manage membership, delete tasks
- Members: see only their projects, create and edit tasks, cannot delete

## Docs to keep current

`docs/decisions.md` — log every real design choice made (what, what was rejected, why). Minimum 5 entries required for submission. `docs/ai-prompts.md` — log every significant prompt used. These are assessed.
