# Submission

## Links

- **GitHub repository:** https://github.com/chauhanabhay568/Project-Task-Tracker
- **Live application:** https://project-task-tracker.up.railway.app

## Notes for the reviewer

Railway's free tier sleeps after inactivity — the first request after a quiet period can take up to 30 seconds to wake. If the page doesn't load immediately, wait a moment and refresh.

Demo data is pre-seeded. Log in with either credential below and you will see projects, tasks across every status, comments, history, overdue alerts, and a blocked task.

## Demo credentials

| Role    | Email             | Password  |
|---------|-------------------|-----------|
| Manager | alice@demo.com    | demo1234  |
| Manager | bob@demo.com      | demo1234  |
| Member  | carol@demo.com    | demo1234  |
| Member  | dave@demo.com     | demo1234  |
| Member  | eve@demo.com      | demo1234  |

## Stack

| Layer    | What you used                          | Why                                                                 |
|----------|----------------------------------------|---------------------------------------------------------------------|
| Frontend | Django templates, plain HTML/CSS       | No JS framework needed — server-rendered HTML keeps things simple   |
| Backend  | Django 4.2, Python                     | Fast to build, excellent ORM, built-in auth, class-based views      |
| Database | SQLite (local), Postgres (production)  | SQLite for dev speed; Postgres on Railway for the live deployment   |
| Hosting  | Railway                                | Free tier, Postgres add-on, easy env var management, GitHub deploy  |

## Goal checklist

| #  | Goal                          | Status  | Notes                                                                                          |
|----|-------------------------------|---------|------------------------------------------------------------------------------------------------|
| 1  | Accounts and roles            | Done    | Manager and member roles, enforced server-side via decorator and mixins                        |
| 2  | Projects                      | Done    | Create, edit, archive, restore — all manager-only                                              |
| 3  | Tasks inside projects         | Done    | Full CRUD, blockers via TaskBlocker join table, tasks listed on project detail                 |
| 4  | Task lifecycle with rules     | Done    | Strict transition table in transitions.py, blocked/unblock, Done gate, illegal moves rejected  |
| 5  | Assignment                    | Done    | Assign/unassign, project-member-only restriction, cascade unassign on member removal, My Tasks |
| 6  | Finding things                | Done    | Server-side search, filters (project/status/priority/assignee/overdue), sort, pagination       |
| 7  | Bulk actions + CSV export     | Partial | CSV export done. Bulk status/assignee/due-date with per-task results not yet built.            |
| 8  | Dashboard                     | Done    | Stat cards, assignee breakdown, 8-week completions chart                                       |
| 9  | History you cannot rewrite    | Done    | Status, assignment and task-field edits all logged via audit.py, comments append-only, unified timeline |
| 10 | Overdue alerts                | Done    | Alert list, nav badge, per-user dismissal with due-date snapshot so alerts reappear on change  |

## How much time did you actually spend?

Roughly 10–11 hours spread across several sessions — about 2 hours a day over a week, as suggested.

## What would you do next, with another 12 hours?

Bulk actions (the missing half of goal 7) would be first — it's the only required feature not fully built. After that: cycle detection across chains of blockers (today two tasks can block each other and both get stuck, which the server permits), then a proper drag-and-drop board view as a stretch feature, and finally email notifications for overdue tasks.

## What are you least happy with in this codebase, and why?

`TaskDetailView.get_context_data` is doing too much — building the timeline, fetching assignees, computing legal next statuses, all in one method. It works, but it should be split into smaller pieces or moved into a service function so it's testable independently. Right now testing it means going through the full view stack.
