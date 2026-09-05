from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Case, F, IntegerField, Q, Value, When
from django.utils import timezone

from .audit import log_change
from .models import AlertDismissal, Task, TaskAssignment, TaskBlocker

if TYPE_CHECKING:
    from .models import Project, User


def active_alerts_for_user(user):
    from django.db.models import F
    from .models import User as UserModel

    today = timezone.now().date()
    qs = Task.objects.filter(
        due_date__lt=today,
        project__archived=False,
    ).exclude(status=Task.Status.DONE)

    if user.role != UserModel.Role.MANAGER:
        qs = qs.filter(project__memberships__user=user)

    # A dismissal is "still valid" only when its due_date_at_dismissal snapshot
    # matches the task's current due_date. If the due date was changed after
    # dismissal, the alert reappears.
    valid_dismissal_ids = AlertDismissal.objects.filter(
        user=user, due_date_at_dismissal=F("task__due_date")
    ).values_list("task_id", flat=True)

    return qs.exclude(pk__in=valid_dismissal_ids).distinct()


def sync_blockers(task: Task, blocking_tasks) -> None:
    blocking_ids = {t.pk for t in blocking_tasks}
    TaskBlocker.objects.filter(blocked_task=task).exclude(
        blocking_task_id__in=blocking_ids
    ).delete()
    for blocking_task in blocking_tasks:
        TaskBlocker.objects.get_or_create(
            blocked_task=task, blocking_task=blocking_task
        )


def cascade_unassign(user: "User", project: "Project", actor: "User | None") -> int:
    assignments = TaskAssignment.objects.filter(
        task__project=project, user=user
    ).select_related("task")

    count = 0
    for assignment in assignments:
        log_change(assignment.task, "assignee", str(user), None, actor)
        assignment.delete()
        count += 1

    return count


def filtered_task_queryset(user, params):
    from .models import User as UserModel

    qs = Task.objects.select_related("project")

    if user.role != UserModel.Role.MANAGER:
        qs = qs.filter(project__memberships__user=user)
    qs = qs.filter(project__archived=False)

    # Filter values arrive straight from the query string, so an id that is not
    # a number is ignored rather than allowed to raise ValueError deep in the ORM.
    project_id = params.get("project")
    if project_id and str(project_id).isdigit():
        qs = qs.filter(project_id=project_id)
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("priority"):
        qs = qs.filter(priority=params["priority"])
    assignee_id = params.get("assignee")
    if assignee_id and str(assignee_id).isdigit():
        qs = qs.filter(assignments__user_id=assignee_id)
    if params.get("overdue") == "1":
        qs = qs.filter(due_date__lt=timezone.now().date()).exclude(status=Task.Status.DONE)

    q = params.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    sort = params.get("sort")
    if sort == "priority":
        # Priority is stored as text, so ordering by the column would sort
        # alphabetically ("low" before "medium"). Rank it by severity instead.
        qs = qs.annotate(
            priority_rank=Case(
                When(priority=Task.Priority.CRITICAL, then=Value(0)),
                When(priority=Task.Priority.HIGH, then=Value(1)),
                When(priority=Task.Priority.MEDIUM, then=Value(2)),
                When(priority=Task.Priority.LOW, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by("priority_rank")
    elif sort == "updated":
        qs = qs.order_by("-updated_at")
    else:
        # Default (and explicit "due_date"): soonest first, with undated tasks
        # last rather than sorting ahead of genuinely overdue work.
        qs = qs.order_by(F("due_date").asc(nulls_last=True))

    return qs.distinct()


def assign_user_to_task(task, user, actor):
    from .models import ProjectMembership, TaskAssignment

    if not ProjectMembership.objects.filter(project=task.project, user=user).exists():
        return False, f"{user.username} is not a member of this project and cannot be assigned."
    assignment, created = TaskAssignment.objects.get_or_create(task=task, user=user)
    if created:
        log_change(task, "assignee", None, str(user), actor)
    return True, f"Assigned to {user}."


def dashboard_stats(user):
    from datetime import date, timedelta
    from django.db.models import Count
    from .models import HistoryEntry, Project, User as UserModel

    today = date.today()

    # Base task queryset scoped by role
    tasks = Task.objects.filter(project__archived=False)
    if user.role != UserModel.Role.MANAGER:
        tasks = tasks.filter(project__memberships__user=user).distinct()

    total = tasks.count()
    done = tasks.filter(status=Task.Status.DONE).count()
    in_progress = tasks.filter(status=Task.Status.IN_PROGRESS).count()
    blocked = tasks.filter(status=Task.Status.BLOCKED).count()
    overdue = tasks.exclude(status=Task.Status.DONE).filter(due_date__lt=today).count()

    # Assignee breakdown — top 5 members by open task count
    assignee_rows = (
        tasks.exclude(status=Task.Status.DONE)
        .filter(assignments__isnull=False)
        .values("assignments__user__username")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )
    assignee_breakdown = [
        {"name": r["assignments__user__username"], "count": r["count"]}
        for r in assignee_rows
    ]

    # 8-week completions — count HistoryEntry rows where status changed to Done
    weeks = []
    history_qs = HistoryEntry.objects.filter(
        field_name="status", new_value=Task.Status.DONE
    )
    if user.role != UserModel.Role.MANAGER:
        history_qs = history_qs.filter(
            task__project__memberships__user=user
        ).distinct()

    for i in range(7, -1, -1):
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        count = history_qs.filter(
            changed_at__date__gte=week_start,
            changed_at__date__lte=week_end,
        ).count()
        weeks.append({"label": week_start.strftime("%-d %b"), "count": count})

    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "blocked": blocked,
        "overdue": overdue,
        "assignee_breakdown": assignee_breakdown,
        "weeks": weeks,
    }


def set_due_date(task, new_due_date, actor):
    old_due_date = task.due_date
    task.due_date = new_due_date
    task.save()
    log_change(task, "due_date", old_due_date, new_due_date, actor)
    return True, f"Due date updated to {new_due_date}."
