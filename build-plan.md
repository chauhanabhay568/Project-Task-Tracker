# Build Plan — Project & Task Tracker

Assumes Django as the stack. Session order is based on dependency, not goal number — some
goals need groundwork from others (e.g. the audit-log mechanism needs to exist *before* task
editing is built, or it has to be retrofitted into five places later).

Total: ~13 hours across 7 sessions, slightly over the 12-hour size guide, which is fine since
it's a guide, not a hard cap.

---

## Session 1 (~2h) — Setup, models, and audit-log foundation
**Goals touched:** groundwork for 2, 3, 5, 9, 10

1. Create the Django project, a git repo, first commit ("project scaffold").
2. Design and write **all** models up front, even before there's UI for them — schema changes
   later are painful:
   - `User` (extend with a `role` field: manager/member)
   - `Project` (key, name, description, owner FK, `is_archived`)
   - `ProjectMembership` (M2M through table: user ↔ project)
   - `Task` (project FK, title, description, priority, due_date, status)
   - `TaskAssignment` (M2M through table: user ↔ task)
   - `TaskBlocker` (self-referential M2M on Task: "blocked by")
   - `HistoryEntry` (task FK, field, old value, new value, actor, timestamp) — the audit trail
   - `Comment` (task FK, author, body, timestamp) — treat as a subtype of history, or a
     separate timestamped, un-editable table
   - `AlertDismissal` (task FK, user FK, dismissed_at, dismissed_due_date — needed for the
     "reappear when due date changes" rule in goal 10)
3. Run migrations. Commit ("data model v1").
4. Build one generic `record_change()` helper now, before writing any editing feature. Every
   place that later changes a task's status, field, assignee, or due date calls this one
   function. This is what prevents goal 9 from becoming a last-minute scramble.
5. Commit ("audit log helper"). Good moment to draft the first `docs/schema.md` pass and a
   `docs/decisions.md` entry (e.g. why blocking was modeled as self-referential M2M).

---

## Session 2 (~2h) — Auth, roles, and project CRUD
**Goals:** 1, 2

1. Login/logout views and templates.
2. A `manager_required` decorator or mixin, used on every manager-only view (create/archive
   project, edit membership, delete task). This is the server-side enforcement for goal 1 —
   test it by hitting a manager-only URL as a Member and confirming it's blocked, not just
   hidden.
3. Project list view — filtered to "projects I'm a member of" for Members, "all" for Managers.
4. Project create/edit views (managers only).
5. Archive/restore actions — flip `is_archived`, keep the row and its tasks intact, exclude
   archived projects from default list views.
6. Commit after each piece (login, then project CRUD, then archive/restore) — don't batch
   these into one commit.

---

## Session 3 (~2h) — Tasks and the lifecycle state machine
**Goals:** 3, 4 (highest-risk goal — budget real time here)

1. Task create/edit/delete views inside a project.
2. Write the transition logic as one function, not scattered `if` statements in the view:
   given a task's current status and a requested new status, return "allowed" or a rejection
   reason. Rules to encode exactly:
   - Backlog → In Progress → In Review → Done (forward, one step at a time)
   - Blocked is only reachable from In Progress or In Review
   - Unblocking returns to whichever state it was blocked *from* (store this, e.g.
     `blocked_from` field)
   - Done → reopened is allowed
   - Moving to Done is rejected if any blocking task isn't Done
   - Every other jump is rejected with a message
3. Every successful transition calls `record_change()` from Session 1.
4. In the template, only render buttons for currently-legal transitions (call the same
   function to decide what to show).
5. Write a couple of quick tests for the transition function specifically — it's the part
   most likely to get probed on the follow-up call.
6. Commit ("task CRUD"), then commit again ("lifecycle transitions") — keep these separate.

---

## Session 4 (~2h) — Assignment, comments, and the timeline view
**Goals:** 5, and the comment/timeline half of 9

1. Assign/unassign UI on the task detail page, restricted to that project's members only.
2. When a manager removes someone from a project, cascade-unassign them from that project's
   tasks — write this as one function, call it from the membership-removal view.
3. "My tasks" view — all tasks assigned to the current user, across every project.
4. Comment form on the task detail page — no edit, no delete, ever (don't even build those
   routes).
5. Render the timeline: creation, field changes, assignment changes, comments, merged and
   sorted by timestamp. This is a formatted read of `HistoryEntry` + `Comment`.
6. Commit incrementally: assignment, then cascade-unassign, then comments/timeline.

---

## Session 5 (~2h) — Search, filters, and bulk actions
**Goals:** 6, 7

1. Main cross-project task list view. Build the queryset server-side: text search
   (`icontains` on title/description), filters (project, status, assignee, priority,
   overdue), sorting (due date, priority, last update), pagination with a total count. Do not
   load everything into the browser.
2. Multi-select checkboxes on that list, posting to a bulk-action endpoint.
3. The bulk endpoint loops over each selected task, runs it through the same validated
   functions from Session 3/4 (transition function, assignment function), and collects a
   per-task result: succeeded / rejected + reason. Return a results table, not a single
   pass/fail.
4. CSV export button that serializes whatever the current filters return.
5. Commit: search/filter first, then bulk actions, then CSV export — three separate commits.

---

## Session 6 (~2h) — Dashboard and alerts
**Goals:** 8, 10

1. Dashboard aggregates: open, overdue, due this week, completed this week — a handful of
   `.aggregate()`/`.count()` queries.
2. Breakdown by status and by assignee (`.values().annotate(Count(...))`).
3. Completions over the last 8 weeks — group `HistoryEntry` rows where the new value is
   "Done" by week. A small Chart.js snippet fed by this as JSON is enough; no need for a full
   JS charting framework.
4. Overdue alerts: query tasks where `due_date < today` and status isn't Done, excluding ones
   the current user has an active `AlertDismissal` for. Nav badge = count of those.
5. Dismiss action: create an `AlertDismissal` row tied to the task's current due date. When
   editing a task, if the due date changes, either delete the matching dismissal or check the
   stored due date against the dismissal's stored due date when computing "is this still
   dismissed" — either approach satisfies "the alert comes back."
6. Commit: dashboard first, then alerts.

---

## Session 7 (~1–2h) — Seed data, deployment, and docs
The session most people skip time for, and it's graded directly.

1. Write a management command that seeds: a few users of both roles, several projects
   (including one archived), tasks spread across every status (including some overdue, some
   blocked, some with comments and history), so the live demo actually shows something
   happening — not an empty shell.
2. Deploy: database first, then the server with its env vars, run migrations + the seed
   command against the live DB, then verify the live URL actually works end to end.
3. Fill in `SUBMISSION.md` fully — links, demo credentials for both roles, stack table,
   honest goal checklist, note if the host sleeps.
4. Finish `docs/architecture.md` (the request path can now be described for real, e.g. "bulk
   status change" end to end) and make sure `docs/decisions.md` has 5+ entries with one
   marked as reversed.
5. Final commit and a last check of the whole commit history — this is what gets read
   closely, so skim it yourself first.

---

## If time runs short

Per the brief, finishing 8 goals solidly beats limping through all 10. Safest things to trim
first (most decoupled from everything else):
- The 8-week completions chart on the dashboard (keep the headline numbers, skip the chart)
- CSV export

Do not cut corners on:
- **Goal 4** (lifecycle rules)
- **Goal 9** (audit trail)

These two are spelled out in the most exact detail in the brief, which usually signals they're
checked most closely.
