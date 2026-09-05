# Decisions

Log the decisions that actually shaped this codebase — the ones where a real alternative existed and
you picked one. At least five entries. For each: what you chose, what you rejected, and why. At least
one entry must be a decision you later reversed — say what changed your mind. It can be any entry
below, not necessarily the last one; add a **Later reversed:** line to whichever one it is.

## Decision 1 — Model task-blocking as a self-referential many-to-many (TaskBlocker) instead of a single FK field

- **Chose:** A separate `TaskBlocker` join table with two FKs both pointing at `Task` (`blocked_task`, `blocking_task`)
- **Rejected:** A single `blocked_by = ForeignKey(Task, null=True)` field directly on the Task model
- **Why:** A single FK can only express "this task is blocked by exactly one other task." In practice a task can be blocked by several things simultaneously — a dependency hasn't shipped, a design decision is pending, and an external API is down. Forcing one blocker per task means users work around the model by picking the "most important" blocker and ignoring the rest, which makes the blocker list unreliable. The join table costs one extra table but correctly represents the real structure: a task has zero or more blockers, and a task can block zero or more others. Both directions are queryable cleanly via `task.blocked_by.all()` and `task.blocks.all()`.

## Decision 2 — Store `pre_blocked_status` on Task instead of inferring it from history

- **Chose:** A dedicated `pre_blocked_status` column on the Task model that is written at the moment a task moves to Blocked
- **Rejected:** Walking `HistoryEntry` backwards at unblock-time to find the last non-Blocked status
- **Why:** Reading history to infer previous state is fragile — it requires the history to be complete and correctly ordered, and it adds a query at exactly the moment you want a simple write. The dedicated column is set once (when the task becomes Blocked) and read once (when the block is lifted). It is never ambiguous. The cost is a nullable column that is only populated for currently-blocked tasks; that is a small, obvious trade.

## Decision 3 — Snapshot `due_date` in AlertDismissal instead of storing only a dismissed flag

- **Chose:** `due_date_at_dismissal` — a copy of `task.due_date` written at dismissal time
- **Rejected:** A simple boolean `is_dismissed` on Task, or a plain (task, user) dismissal record with no date snapshot
- **Why:** The requirement is that a dismissed alert reappears if the due date changes. A boolean flag has no memory of what was true when it was set, so there is no way to detect that the situation has changed. Storing the snapshot makes the check trivial: if `task.due_date != dismissal.due_date_at_dismissal`, the dismissal is stale and the alert should show again. This is the only denormalised field in the schema and it exists specifically to support this one rule without needing a background job or extra query logic.

## Decision 4 — Use explicit join models (ProjectMembership, TaskAssignment) instead of Django's ManyToManyField

- **Chose:** Explicit model classes for both join tables
- **Rejected:** `ManyToManyField` on User or Project/Task pointing at the other side
- **Why:** Django's `ManyToManyField` is convenient when the join table has no columns of its own. Both of these tables have a timestamp (`joined_at`, `assigned_at`) that we want to record and potentially display ("assigned 3 days ago"). Adding a `through` model to a `ManyToManyField` later is possible but requires a migration and changes the query API. Starting with explicit models costs nothing extra and keeps the door open for adding more data to the relationship later without restructuring.

## Decision 5 — Comments are append-only with no edit or delete views, ever

- **Chose:** `Comment` model with no update or delete endpoint, enforced by convention (no views built, documented in code and schema docs)
- **Rejected:** Full CRUD on comments the way most apps handle them
- **Why:** Comments on a task serve as a timestamped discussion record and partial audit trail. If comments can be edited or deleted, a user can rewrite history — "I said this was approved" becomes unprovable. Append-only comments are a meaningful guarantee to the whole team. The DB does not enforce this natively (no row-level INSERT-only constraint without triggers), so it is enforced at the application layer by simply never building the edit/delete views. The constraint is documented in the model file and here so that any future developer understands it is intentional, not an oversight.

## Decision 6 — Enforce project access in one mixin on every project-scoped view, not only on task views

- **Chose:** A single `ProjectAccessMixin` that resolves the project and checks manager-or-membership, applied to every view that touches a project — including `ProjectDetailView` and `DismissAlertView`
- **Rejected:** Relying on the list queries being scoped correctly and the templates never linking anywhere a user shouldn't go
- **Why:** The original reasoning was that `ProjectListView` already filters to a member's own projects, so a member would never be handed a link to someone else's project detail page — the scoped list *was* the access control. That reasoning is wrong in a way that is easy to miss: it protects the path through the UI and leaves the URL itself open. Anyone who edits the number in `/projects/3/` walks straight in. The brief says this explicitly — "the difference must be enforced on the server, not just hidden in the interface" — and I had applied that rule to the manager-only actions while quietly assuming read access didn't need it.
- **Later reversed:** Yes. I originally shipped `ProjectDetailView` as a plain `LoginRequiredMixin, DetailView` with no membership check, and only enforced project access on the task views. A written test that logged in as a member of Project One and requested Project Two's detail page came back **200**, with the other project's name and task titles rendered in the response. I reversed the decision and moved the check into the mixin so it covers every project-scoped view by construction rather than by my remembering to add it. The same reversal fixed `DismissAlertView`, which had no access check at all for the same reason — I had thought of dismissal as a harmless personal preference rather than as a write against a task the user may not be entitled to see.
- **Cost of the reversal:** the mixin had to learn that for a project view the resolved object *is* the project, rather than something with a `.project` attribute. That is four lines, and it is the reason the check is now impossible to forget on a new view.

## Decision 7 — Dismissing an overdue alert requires being assigned to the task, even for managers

- **Chose:** `DismissAlertView` rejects anyone not in the task's `TaskAssignment` rows, and the alerts page renders "Not assigned to you" in place of the button
- **Rejected:** Letting any project member dismiss, or carving out an exception so managers can clear alerts across their whole portfolio
- **Why:** The brief is specific — "a person can dismiss an alert for a task they are assigned to" — and dismissal is per-user state, so a manager clearing an alert would only ever hide it from themselves anyway. The wider reading would also let one member silence a warning about work that is not theirs. The trade-off is real and I want it on the record: a manager watching the portfolio sees every overdue task and can dismiss almost none of them, which is arguably the wrong ergonomics for the person most likely to be triaging. If that turned out to be annoying in practice, the fix is to widen the check to project membership in one place — but I would rather match the stated requirement than guess at an unstated one.
