# Schema

## Tables and columns

### tracker_user
Extends Django's built-in auth_user table (which gives us id, username, password, email, is_staff, etc.) and adds:
- `role` — varchar, one of "manager", "member"

Django's AbstractUser handles all the authentication machinery. We only own the `role` column.

### tracker_project
- `id` — auto integer primary key
- `key` — short unique varchar (e.g. "PROJ"), used as a prefix in task labels
- `name` — varchar
- `description` — text, optional
- `owner_id` — FK to tracker_user
- `archived` — boolean, default false
- `created_at` — timestamp, set once on creation

### tracker_projectmembership
- `id` — auto integer primary key
- `user_id` — FK to tracker_user
- `project_id` — FK to tracker_project
- `joined_at` — timestamp, set once on creation
- Unique constraint on (user_id, project_id)

### tracker_task
- `id` — auto integer primary key
- `project_id` — FK to tracker_project
- `title` — varchar
- `description` — text, optional
- `priority` — varchar, one of "low", "medium", "high", "critical"
- `due_date` — date, optional
- `status` — varchar, one of "backlog", "in_progress", "in_review", "blocked", "done"
- `pre_blocked_status` — varchar, same choices as status, nullable
- `created_at` — timestamp, set once on creation
- `updated_at` — timestamp, updated on every save

### tracker_taskassignment
- `id` — auto integer primary key
- `user_id` — FK to tracker_user
- `task_id` — FK to tracker_task
- `assigned_at` — timestamp, set once on creation
- Unique constraint on (user_id, task_id)

### tracker_taskblocker
- `id` — auto integer primary key
- `blocked_task_id` — FK to tracker_task
- `blocking_task_id` — FK to tracker_task
- Unique constraint on (blocked_task_id, blocking_task_id)

Both FKs point at the same table. One row means "blocking_task is preventing blocked_task from moving forward."

### tracker_historyentry
- `id` — auto integer primary key
- `task_id` — FK to tracker_task
- `field_name` — varchar (e.g. "status", "due_date", "priority")
- `old_value` — text, nullable
- `new_value` — text, nullable
- `changed_by_id` — FK to tracker_user, nullable (SET_NULL so rows survive user deletion)
- `changed_at` — timestamp, set once on creation

### tracker_comment
- `id` — auto integer primary key
- `task_id` — FK to tracker_task
- `author_id` — FK to tracker_user, nullable (SET_NULL)
- `text` — text
- `timestamp` — timestamp, set once on creation

Comments are append-only. No update or delete path exists anywhere in the codebase.

### tracker_alertdismissal
- `id` — auto integer primary key
- `task_id` — FK to tracker_task
- `user_id` — FK to tracker_user
- `dismissed_at` — timestamp, set once on creation
- `due_date_at_dismissal` — date (snapshot of task.due_date at the moment of dismissal)
- Unique constraint on (task_id, user_id)

---

## Relationships

### One-to-many (ForeignKey)
These are cases where one record owns many others and there is a clear parent:

| Parent | Child | Meaning |
|---|---|---|
| User | Project | a user owns many projects |
| Project | Task | a project contains many tasks |
| Task | HistoryEntry | a task accumulates many history rows |
| Task | Comment | a task accumulates many comments |
| Task | AlertDismissal | a task can be dismissed by many users |

### Many-to-many (explicit join tables)
These are cases where neither side owns the other — the relationship itself is the thing:

| Table A | Join model | Table B | Why explicit instead of ManyToManyField |
|---|---|---|---|
| User | ProjectMembership | Project | We store `joined_at` on the relationship |
| User | TaskAssignment | Task | We store `assigned_at` on the relationship |
| Task | TaskBlocker | Task (self) | Self-referential; we need both directions queryable |

Django's built-in `ManyToManyField` is fine when the join table has no extra columns. As soon as you need data on the relationship itself (a timestamp, a role, a snapshot), you make it an explicit model.

---

## Constraints: database vs application code

**Enforced by the database:**
- `unique_together` on ProjectMembership, TaskAssignment, TaskBlocker, AlertDismissal — duplicates are impossible even under concurrent writes
- `NOT NULL` on required fields — bad data cannot be inserted even if application code has a bug
- `PROTECT` on Project.owner — the DB refuses to delete a user who owns a project
- `CASCADE` on Task, Membership, Assignment, etc. — deleting a project wipes its tasks automatically

**Enforced by application code only:**
- Status transition rules (e.g. you can't go from Done back to Backlog) — too dynamic for a DB constraint
- `pre_blocked_status` must be set before moving a task to Blocked — the DB just sees a nullable varchar
- Comment append-only rule — the DB has no concept of "only allow INSERT, not UPDATE/DELETE on this table" without triggers; we enforce it by simply not building edit/delete views

The line: anything that can be expressed as a column constraint or a FK rule belongs in the DB. Business rules that require reading other rows or knowing the current user belong in application code.

---

## Deliberate denormalisation

`due_date_at_dismissal` on AlertDismissal is the only intentional denormalisation. It duplicates `task.due_date` at a point in time rather than always reading the live value. This is intentional: the "alert reappears if due date changes" rule depends on knowing what the due date *was* when the user dismissed it, not what it is now.

`old_value` and `new_value` on HistoryEntry also store copies of data that lives elsewhere. This is necessary for an audit log — the whole point is that it reflects past state, not current state.

---

## What breaks first at 100x data

`tracker_historyentry` grows the fastest — every field change on every task writes a row. At scale this table dwarfs all others. Queries like "show full history for task X" stay fast (indexed on task_id), but "show all changes made by user Y across all projects" would need a separate index on `changed_by_id`.

`tracker_comment` has the same growth pattern for active projects.

The `tracker_taskblocker` self-join is fine as long as blocker chains don't get deep — detecting circular dependencies (Task A blocks B blocks A) requires a graph traversal that the DB cannot do natively; at scale that moves to application code or a graph store.
