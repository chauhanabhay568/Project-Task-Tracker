# Assignment 01 — Project & Task Tracking

## The scenario

Picture a services company running work for a dozen or so client projects at any given time — some
short engagements, some long retainers, each with its own priorities and its own deadlines. The same
people often work more than one of these projects in a given week, moving between them as things get
busy or quiet. Right now none of that coordination lives in one place: task lists sit in
spreadsheets that only one person remembers to update, status gets typed into chat threads and then
scrolls out of view, and due dates mostly exist in people's heads.

The result is predictable. A manager finds out a deadline was missed when the client brings it up,
not before. Nobody can answer 'what is overdue' across the whole portfolio with any confidence, or
say which of their people is quietly buried under four projects while another has nothing this week.
When someone asks why a task stalled, the honest answer is usually to go ask around, and by the time
an answer comes back the moment to do anything about it has often passed.

They want one internal tool to replace all of it: somewhere managers set up projects, decide who is
on each one, and see the whole portfolio at a glance, and somewhere staff go to see what is theirs
and move it forward. Anyone should be able to get a straight answer to 'what is overdue' or 'who is
overloaded' without asking around to find out. That is what you are building.

## What it must do

Everything below is required. Several of the ten spell out exact rules — what happens on an illegal
move, what a bulk action must report back, when a dismissed alert is allowed to reappear — and those
specifics are the actual ask, not just the bold headline in front of them.

1. **Accounts and roles.** People sign in with an email and password, and there are at least two
roles — a manager role and a regular member role. Managers can create and archive projects, change
who is on a project, and delete tasks. Members can do neither, and only see projects they belong to.
The difference must be enforced on the server, not just hidden in the interface.

2. **Projects.** Managers create projects with a short key, a name, a description and an owner, and
can edit them later. Projects can be archived and restored. Archiving hides a project from the
default views without destroying its data or its tasks.

3. **Tasks inside projects.** Every task belongs to exactly one project and carries a title, a
description, a priority, an optional due date, and any number of other tasks in the same project
that block it. Tasks can be created, edited, and deleted. Opening a project shows its tasks.

4. **A task lifecycle with rules.** A task moves through *Backlog → In Progress → In Review → Done*,
and can be marked *Blocked* from either In Progress or In Review. Unblocking returns it to the state
it was blocked from. A finished task can be reopened. A task with an unfinished blocking task cannot
move to Done — the server rejects the attempt. Any other jump — Backlog straight to Done, for
instance — must be rejected by the server with a message explaining why, and the interface should
only offer the moves that are currently legal.

5. **Assignment.** A task can have any number of people assigned to it, and a person can hold many
tasks. Only members of a task's project may be assigned to it, and removing someone from a project
unassigns them from that project's tasks. Every user can see one list of everything assigned to them
across all projects.

6. **Finding things.** One list shows tasks across every project the viewer can see, with a text
search over titles and descriptions, filters for project, status, assignee, priority and overdue,
sorting by due date, priority or last update, and pagination showing the total number of matches.
All of this must be done by the server — do not load every task into the browser and filter there.

7. **Acting on many tasks at once.** Select several tasks from the list and apply one change to all
of them: a status move, an assignee change, or a new due date. Because some of those changes will be
illegal for some tasks, the result must report per task what succeeded and what was rejected and why
— not just fail the whole batch. Separately, export the currently filtered list as a CSV file.

8. **A dashboard.** A landing view shows headline numbers — open tasks, overdue tasks, due this
week, completed this week. It also breaks tasks down by status and by assignee, and charts
completions over the last eight weeks.

9. **History you cannot rewrite.** Every task has a timeline showing when it was created, every
field change with the old and new value and who made it, every assignment and unassignment, and any
comments people have left. Comments are part of this timeline. Nothing in the timeline can be edited
or deleted after the fact, including by managers.

10. **Overdue alerts.** Tasks that are past their due date and not finished appear in an alerts
area, with a count badge visible in the navigation. A person can dismiss an alert for a task they
are assigned to. If that task's due date later changes, the alert comes back.

## Stretch ideas (optional)

None of these are required, and none substitute for a goal above. If you finish all ten with time
left over, pick whichever of these sounds most useful and build it:

- A drag-and-drop board view.
- Cycle detection across chains of task dependencies, beyond a single blocking relationship.
- Time tracking.
- Saved filter views.
- @-mentions in comments.
- An email digest of overdue work.
- Per-project custom fields.
- An activity feed across all projects.
- Keyboard-driven navigation.


---

## What we are assessing

A working application is table stakes. Almost every serious candidate will produce something that runs, has a login, and roughly does what was asked. That's the floor, not the differentiator.

What actually separates submissions is the record of thinking behind the app: the decisions you made and why, the trade-offs you weighed, what you built first and what you deliberately left out, and whether you can explain any part of your own system when asked. We are hiring for judgement. The app is the evidence for that judgement, not the deliverable in itself.

We also read the code itself for structure and readability, which counts for a small share of the overall score.

## Time budget

Budget about 12 hours total, spent roughly 2 hours a day across a week.

This is not a race. We are not timing you against other candidates, and submitting early scores nothing extra. Twelve hours is a size guide so you know how much to attempt — pace yourself, stop when you're tired, and spend some of that time thinking and documenting, not only typing code.

## Pick any stack you like

Use any language, any framework, any UI library, any ORM, and any database access approach you want. We have no house stack, and no stack scores better than another — this round is not a test of whether you know particular tools.

Use whatever you are fastest and most confident in. Time spent learning something new to impress us is time not spent on the ten goals above, and it will show.

## Using AI is allowed and encouraged

Use AI tools however you want — to scaffold code, debug a stuck problem, write tests, draft documentation, or anything else that helps you move faster. A few things to know about how we treat it:

- We do not penalise AI use, and we make no attempt to detect it.
- We care about whether you understood, directed and verified the output — not about who or what produced the first draft of it.
- `docs/ai-prompts.md` must contain the prompts you actually used, including the ones that produced bad output and what you changed afterwards. If you used no AI at all, say so here and describe how you worked instead — that is assessed the same way.
- Submitting generated code you cannot explain is the single most common way candidates fail this round.

You are accountable for everything in your submission. If a reviewer points at a piece of code and asks why it's there, or why it works the way it does, "the AI wrote it" is not an answer.

## Use git properly

Publish to a public GitHub repository, and commit incrementally as the work actually happens — after each meaningful step, not in one pass at the end.

A repository whose entire history is a single "initial commit" containing a finished app scores zero on git history, and it colours how we read everything else in your submission, however good the app itself is. Your history is how we see the order you built in, where you got stuck, and how the design changed along the way. If it isn't there, we can't assess it, and we won't assume the best.

## What you must commit

Alongside your code, commit these five files under `docs/`. Your zip includes a stub for each with the questions it needs to answer — fill them in as you go, not from memory at the end.

| File | What it must answer |
|------|----------------------|
| `docs/architecture.md` | What the moving pieces are, how they talk to each other, where each one runs, the request path for one representative user action end to end, and what you decided not to build. |
| `docs/schema.md` | Every table's columns and types, which relationships are one-to-many versus many-to-many, which constraints live in the database versus the application, what you deliberately denormalised, and what would break first at 100x the data. |
| `docs/plan.md` | How you split the work into sessions, what order you built in and why, what you estimated versus what it actually took, and what you cut when you ran short. |
| `docs/decisions.md` | At least five real decisions — what you chose, what you rejected, and why — including at least one you later reversed. |
| `docs/ai-prompts.md` | The prompts you actually used, in order, grouped by what you were trying to do, including at least one that produced something wrong and what you did about it. |

## Host it for free

Deploy the whole thing somewhere reachable by URL, using free tiers only.

One combination that works, if you would rather not decide:

- **Database** — a managed service such as Supabase.
- **Server-side code** — Render.
- **Browser-side code** — Vercel.

Deploy in that order: create the database first, give the server its connection details as environment variables, then point the browser-side part at the server's public URL.

This is one option, not a requirement. Any free host is equally acceptable — everything on a single provider, one virtual machine, a container platform, a static host with serverless functions. The choice earns and loses nothing.

Requirements:

- A working live URL.
- Seeded with enough demo data to show the system doing something, not an empty shell.
- Demo credentials for every role recorded in `SUBMISSION.md`.
- Connection strings, keys and passwords kept in environment variables, never in the repository.
- Free tiers often sleep when idle and can take a minute or more to wake. Note it in `SUBMISSION.md` if yours does, so a slow first load is not read as a broken deployment.
- If you cannot get it hosted, submit anyway and record in `SUBMISSION.md` what you tried and where it broke.

## How to submit

Send us:

- The URL of your public GitHub repository.
- The URL of your live, deployed application.
- Your completed `SUBMISSION.md`, committed to the repository.

That's the whole submission. Nothing else to prepare, no separate form.

## What happens next

If your submission clears the bar, we'll set up a short call. We will ask about specific decisions we can see in your repository and its history — why you modelled something a particular way, what a certain commit was fixing, what you'd change if you kept going.

We're telling you this now because it should change how carefully you document as you go. Write `docs/decisions.md` for a version of yourself who has to explain it three weeks from now.

## Scope

The 10 goals stated in this brief are the cutoff. Meet all 10, solidly, and you have a complete submission.

Stretch ideas are optional. They exist for candidates who finish the 10 with time left and want to keep building — they are never required, and they do not make up for a goal you didn't hit. Doing 8 goals well beats doing 10 goals badly. If time is short, finish fewer goals properly rather than leaving all ten half-done.
