from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils import timezone

from .audit import log_change
from .models import Task, TaskAssignment

if TYPE_CHECKING:
    from .models import Project, User


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
