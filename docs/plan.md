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

12. **Dashboard** — headline stat cards (total, done, in progress, blocked, overdue), assignee breakdown table, 8-week completions chart drawn on a canvas element without an external library.

13. **CSV export** — export the currently filtered task list as a `.csv` file, reusing the same queryset function the task list uses so filters carry through automatically.

14. **Railway deploy setup** — `Procfile`, environment variable wiring, CSRF trusted origins, WhiteNoise for static files.

15. **Adversarial audit and fixes** — wrote throwaway tests against every implemented goal, hunting edge cases rather than the happy path. Found six real bugs (two of them access-control holes) plus three smaller correctness issues, fixed all nine, and re-ran everything. Details in `ai-prompts.md`; the two access-control fixes are written up in `decisions.md` #6 and #7.

## What order did you build in, and why that order?

**Bottom-up: data model first, then the simplest read/write views, then progressively more complex behaviour.**

- Every layer depends on the one below it — views depend on models, transition logic depends on models and the audit helper, the alert system depends on tasks having due dates and users having the ability to dismiss
- Building top-down would mean writing views against models that don't exist yet, which forces you to guess and then fix
- Starting with the data model forced all the hard structural decisions early (see `decisions.md`) — things like whether to use a join table or a FK, whether to snapshot the due date on dismissal
- Getting those decisions wrong late is expensive; getting them wrong early is cheap

## What did you estimate versus what it actually took?

- **Data model and basic CRUD** — faster than expected, straightforward Django, no surprises
- **Task lifecycle (status transitions)** — took longer than expected; the blocked/unblock flow had tricky edge cases (saving the previous status, the Done gate, only allowing unblock back to the exact prior state)
- **Overdue alerts** — looked simple but wasn't; a plain dismissed flag doesn't work because you need to know what the due date *was* when the user dismissed it, not what it is now — figuring that out needed thinking time before any code was written
- **Dashboard 8-week chart** — took an extra pass to realise completions had to be counted from `HistoryEntry` rows (audit log), not from current task statuses; drawing it on a plain canvas without a library was fine once the data query was right
- **Role correction (unplanned)** — AI generated a three-role system (`admin`, `member`, `viewer`) instead of the brief's two; catching and fixing it before anything was built on top of it cost an unplanned correction step
- **Final audit (badly underestimated)** — I expected this to be a quick confirmation that everything worked and budgeted almost nothing for it. It found six real bugs, including two access-control holes in goals 1 and 10 and a missing history requirement in goal 9, all in features I had manually clicked through and believed were finished. Verification deserved its own session from the start, not the leftover time at the end

## What did you cut when you ran short?

Nothing from the core requirements was cut. The optional stretch features that did not make it in:

- **Email notifications** — would need a mail provider, environment config, and background job or synchronous SMTP. Too much infrastructure for the time available.
- **Real-time updates** — WebSockets or polling. Not in the requirements, not worth the complexity.
- **Pagination on project and membership lists** — added it on the task list because the filtering UI implies many results. Left it off the other lists on the assumption they stay short.
- **Bulk task operations** — selecting multiple tasks and applying a status, assignee, or due date change across all of them with per-task success/failure reporting. Goal 7 from the spec; not yet built.
