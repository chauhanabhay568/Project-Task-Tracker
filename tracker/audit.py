from __future__ import annotations

from typing import TYPE_CHECKING

from .models import HistoryEntry

if TYPE_CHECKING:
    from .models import Task, User

"""
The problem it solves: Later on, lots of different things will change a 
task — someone moves it from "In Progress" to "Done," someone reassigns 
it to a different person, someone updates the due date. Every one of 
those changes needs to get logged into the HISTORYENTRY table 
(the permanent history/audit trail we talked about).
"""
def log_change(
    task: "Task",
    field_name: str,
    old_value,
    new_value,
    changed_by: "User | None",
) -> HistoryEntry:
    return HistoryEntry.objects.create(
        task=task,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        changed_by=changed_by,
    )
