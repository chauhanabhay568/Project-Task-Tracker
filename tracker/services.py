from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q
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

    if params.get("project"):
        qs = qs.filter(project_id=params["project"])
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("priority"):
        qs = qs.filter(priority=params["priority"])
    if params.get("assignee"):
        qs = qs.filter(assignments__user_id=params["assignee"])
    if params.get("overdue") == "1":
        qs = qs.filter(due_date__lt=timezone.now().date()).exclude(status=Task.Status.DONE)

    q = params.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    sort = params.get("sort")
    sort_map = {"due_date": "due_date", "priority": "priority", "updated": "-updated_at"}
    qs = qs.order_by(sort_map.get(sort, "due_date"))

    return qs.distinct()


def assign_user_to_task(task, user, actor):
    from .models import ProjectMembership, TaskAssignment

    if not ProjectMembership.objects.filter(project=task.project, user=user).exists():
        return False, f"{user.username} is not a member of this project and cannot be assigned."
    assignment, created = TaskAssignment.objects.get_or_create(task=task, user=user)
    if created:
        log_change(task, "assignee", None, str(user), actor)
    return True, f"Assigned to {user}."


def set_due_date(task, new_due_date, actor):
    old_due_date = task.due_date
    task.due_date = new_due_date
    task.save()
    log_change(task, "due_date", old_due_date, new_due_date, actor)
    return True, f"Due date updated to {new_due_date}."
