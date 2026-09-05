# AI Prompts

## Process note

This project used two AI tools in two different roles, and it's worth being explicit about
the split:

- **Claude (chat)** was used as a planning and code-review layer: breaking the brief into
  sessions, working out the exact rules for ambiguous parts of the spec (e.g. what state a
  reopened task returns to), writing precise natural-language instructions for each step, and
  — critically — independently checking the actual GitHub repository against those
  instructions after each step, rather than just trusting that a prompt had been followed
  correctly.
- **Claude Code** was the tool that actually wrote and ran the Django code, one step at a
  time, from the instructions produced above.

Every prompt below is a real instruction that was actually given to Claude Code during this
build, condensed for this log where the original was long. Grouped by session/goal.

## Session 1 — models and audit-log foundation (groundwork for goals 2, 3, 5, 9, 10)

**Prompt:** Set up the Django project and app, configure a custom `User` model with a `role`
field before the first migration runs, then write all nine models (`User`, `Project`,
`ProjectMembership`, `Task`, `TaskAssignment`, `TaskBlocker`, `HistoryEntry`, `Comment`,
`AlertDismissal`) as specified, generate and apply migrations, and write one reusable
`log_change(task, field_name, old_value, new_value, changed_by)` function that is the only
code path allowed to write to `HistoryEntry`.

**Result:** Correct on the first pass. Verified directly by reading the resulting
`models.py` and `audit.py` against the spec, and by running `makemigrations`/`migrate`
successfully.

## Session 2 — auth, roles, project CRUD

**Prompt:** Wire up Django's built-in login/logout views with email-style login, build a
`manager_required` decorator enforcing role-based access server-side (not just hiding UI),
and add project list/create/edit/archive/restore views scoped correctly by role.

**Result — one thing initially wrong:** the first pass of the `User.Role` model used **three**
roles (`admin`, `member`, `viewer`) instead of the brief's two (`manager`, `member`). This was
caught by re-reading the brief's exact wording before building anything on top of it, not by
Claude Code flagging it — it silently generated a working three-role system without pointing
out that it didn't match the spec. **Correction:** a follow-up prompt explicitly instructed
collapsing to two roles (`manager`/`member`) and regenerating the migration, since no real
data existed yet. Everything built afterward used the corrected two-role version.

The `manager_required` decorator itself was tested with an automated test (anonymous →
redirect, member → 403, manager → 200) before being wired onto any real view, and all three
cases passed on the first run.

## Session 3 — task lifecycle (goal 4, highest-risk goal)

**Prompt:** Write `attempt_transition(task, new_status, actor)` encoding the full transition
rule table (forward-only progression, Blocked only from In Progress/In Review, unblocking
returns to the stored prior status, Done requires all blockers finished, Done can reopen),
have it call `log_change` on every successful transition, and write automated tests covering
every row of the table plus the two "trap" cases (that unblocking returns to the *correct*
specific prior state, not a hardcoded one; and that the Done-blocker check actually blocks and
then un-blocks correctly once the blocker finishes).

**Result:** Correct, and verified by actually running `python manage.py test tracker -v 2`
rather than trusting a "tests passed" summary — all cases passed, including the two trap
cases.

**Note on an underspecified rule, not a wrong output:** the brief says a Done task "can be
reopened" but never states which status it returns to. This wasn't something Claude Code got
wrong — it was a genuine gap in the brief that had to be resolved by a human decision (see
`docs/decisions.md`, #3) before the prompt could even be written precisely.

## Session 4 — assignment, membership, comments, timeline (goal 5, half of goal 9)

**Prompt (in two parts, run out of original order):** First, add project membership
management (add/remove a member, manager-only) — then task assignment restricted strictly to
actual project members (not "manager or member") — then cascade-unassignment wired into the
membership-removal view — then a "My Tasks" cross-project view — then commenting and a merged,
time-sorted timeline combining task creation, every `HistoryEntry` row, and every `Comment`.

**Result — a planning gap, not a code gap:** the *original session plan* didn't include
project membership management as a step at all, even though goal 1 requires it and goal 5's
cascade-unassign rule depends on it existing. This was caught by checking the brief's exact
wording against the actual repository before writing the assignment prompt, and the plan was
revised to add it as a new first step. Once prompted correctly, Claude Code's implementation
of all five pieces was verified directly against the repo and, for the tricky parts
(assignment eligibility, cascade count, timeline merge/sort order), traced through by hand —
no further corrections needed.

## Session — search, filters (goal 6)

**Prompt:** Build one cross-project task list with server-side text search (title +
description), filters (project/status/priority/assignee/overdue), sorting, and real
pagination with a total count — explicitly not client-side filtering of a fully-loaded list.

**Result:** Correct as specified.

## Session — blocking-task UI, overdue alerts (goal 3 gap, goal 10)

**Prompt:** Add a "blocked by" multi-select to the task form (syncing `TaskBlocker` rows
manually, since it's a through-table rather than a direct many-to-many field), display
blockers on the task detail page, then build the overdue-alerts query, a nav badge, and a
dismiss action using a due-date snapshot so a dismissed alert correctly reappears if the due
date later changes.

**Result:** Correct as specified; the due-date-snapshot reappearance rule was specifically
tested by dismissing an alert, then changing the due date, and confirming the alert returned.

## Session — dashboard (goal 8)

**Prompt:** Build headline aggregate counts, status/assignee breakdowns, and an 8-week
completions chart (grouping `HistoryEntry` rows where a task's status changed to Done, by
week), all scoped by the same project-visibility rule as the task list, fed to a simple
Chart.js snippet.

**Result:** Correct as specified.

## Session — bulk actions and CSV export (goal 7)

**Prompt (in four parts):** (A) fix a logging gap — first refactor `TaskUpdateView` to log
every changed field, not just status/assignee; (B) extract assignment logic and add a
due-date-change function into `services.py` so they share a consistent interface with the
existing transition function; (C) build the bulk-action endpoint, looping selected tasks
through those same three functions and collecting a per-task success/failure result rather
than a single pass/fail for the whole batch; (D) add CSV export of the currently filtered
task list.

**Result — the clearest "wrong output" caught in this project:** `TaskUpdateView` had been
silently missing audit logging since Session 3 — editing a task's title, description,
priority, or due date through the normal edit form never wrote to `HistoryEntry`, even though
goal 9 requires "every field change" to appear in the timeline. This was only surfaced while
designing the bulk due-date-change feature: it would have been inconsistent for a *bulk*
due-date change to be logged while an ordinary single-task edit of the same field wasn't.
**Correction:** Part A above was added specifically to close this gap before building
anything bulk-related on top of it, so the fix landed as its own reviewable piece of the
change rather than being buried inside the bulk-actions work.

## If you used no AI for a given part

Not applicable here — AI (in the two roles described above) was used throughout. 