from __future__ import annotations

from typing import TYPE_CHECKING

from .audit import log_change
from .models import TaskAssignment

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
