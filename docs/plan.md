# Plan

## How did you break the work into sessions?

I split the build into small, shippable slices — each session ended with working, runnable code. Nothing was left half-built at the end of a session.

1. **Data model** — defined all the models (`User`, `Project`, `Task`, `ProjectMembership`, `TaskAssignment`, `TaskBlocker`, `HistoryEntry`, `Comment`, `AlertDismissal`) and ran the initial migrations. No views yet — just the database shape.

2. **Audit log helper** — wrote `audit.py` (`log_change`) before the views that would need it, so it was ready to call and not retrofitted later.

3. **Project views** — project list, create, edit. Login and logout. The first thing you can actually click through in the browser.

4. **Archive and restore** — simple next step, two function-based views, no new models.

5. **Task CRUD** — create, detail, edit, delete. Tasks show up inside their project.

6. **Lifecycle transitions** — the status machine (`transitions.py`), status change view, blocking logic. This was the most complex single piece.

7. **Task assignment** — assign and unassign members, cascade unassign when a member is removed from a project.

8. **My tasks view** — personal view of all tasks assigned to the logged-in user.

9. **Comments and timeline** — append-only comments, combined history+comment timeline on the task detail page.

10. **Search and filters on tasks** — the task list with filtering by project, status, priority, assignee.

11. **Overdue alerts** — alert list, dismissal with due date snapshot, context processor to show alert count in the nav.

12. **Railway deploy setup** — `Procfile`, environment variable wiring, CSRF trusted origins, WhiteNoise for static files.

## What order did you build in, and why that order?

Bottom-up: data model first, then the simplest read/write views, then progressively more complex behaviour.

The reason for this order is that every layer depends on the one below it. The views depend on the models. The transition logic depends on the models and the audit helper. The alert system depends on tasks having due dates and users having the ability to dismiss. Building top-down would mean writing views against models that don't exist yet, which forces you to guess and then fix.

Starting with the data model also forced all the hard structural decisions early (see `decisions.md`) — things like whether to use a join table or a FK, whether to snapshot the due date on dismissal. Getting those wrong late is expensive. Getting them wrong early is cheap.

## What did you estimate versus what it actually took?

The data model and basic CRUD were fast — straightforward Django, no surprises.

The transition logic took longer than expected. Getting the blocked/unblocked path right (snapshotting `pre_blocked_status`, the Done gate that checks blockers, the unblock only restoring to the exact previous status) required more careful thinking than a simple status field update. The edge cases are not obvious until you write the tests in your head.

The alert system was also trickier than it looked. The "alert reappears if due date changes" requirement is the interesting part. A naive `is_dismissed` boolean doesn't work — you need the snapshot. Working that out took a few minutes of thinking before writing a line of code.

## What did you cut when you ran short?

Nothing from the core requirements was cut. The optional stretch features that did not make it in:

- **Email notifications** — would need a mail provider, environment config, and background job or synchronous SMTP. Too much infrastructure for the time available.
- **Real-time updates** — WebSockets or polling. Not in the requirements, not worth the complexity.
- **Pagination on project and membership lists** — added it on the task list because the filtering UI implies many results. Left it off the other lists on the assumption they stay short.
- **Bulk task operations** — marking multiple tasks done at once. Not in the spec.
