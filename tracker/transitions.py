from __future__ import annotations

from typing import TYPE_CHECKING

from .audit import log_change
from .models import Task

if TYPE_CHECKING:
    from .models import User

S = Task.Status

# Maps (from_status, to_status) → True for always-allowed transitions.
# Blocked→* and *→Blocked are handled inline because they need side-effects
# or dynamic targets; everything else lives in this table.
_ALLOWED: set[tuple[str, str]] = {
    (S.BACKLOG,      S.IN_PROGRESS),
    (S.IN_PROGRESS,  S.IN_REVIEW),
    (S.IN_REVIEW,    S.DONE),
    (S.IN_PROGRESS,  S.BLOCKED),
    (S.IN_REVIEW,    S.BLOCKED),
    (S.DONE,         S.IN_PROGRESS),
}


def attempt_transition(
    task: Task,
    new_status: str,
    actor: "User | None",
) -> tuple[bool, str | None]:
    """
    Try to move *task* to *new_status* on behalf of *actor*.

    Returns (True, None) on success after saving the task and writing an
    audit entry.  Returns (False, reason) — without touching the DB — when
    the move is illegal.

    Edge cases worth noting:

    **Blocked transitions**
    Moving *into* Blocked snapshots the current status into
    ``task.pre_blocked_status`` so the unblock path can restore it.
    Moving *out of* Blocked is only legal when new_status equals the
    recorded ``pre_blocked_status``.  If that field is somehow empty
    (data-integrity gap), the unblock is rejected rather than guessing.

    **Done gate**
    A task may only reach Done from In Review, and only when every task in
    its ``blocked_by`` set is itself Done.  The check uses
    ``TaskBlocker.blocking_task`` (the task that *blocks* this one) to
    inspect those tasks' statuses.
    """
    old_status = task.status

    # --- unblock path: Blocked → pre_blocked_status ---
    if old_status == S.BLOCKED:
        if not task.pre_blocked_status:
            return (
                False,
                "Cannot unblock: no prior status was recorded for this task.",
            )
        if new_status != task.pre_blocked_status:
            return (
                False,
                f"Cannot move a blocked task directly to '{new_status}'. "
                f"Unblocking restores it to '{task.pre_blocked_status}' only.",
            )
        task.status = new_status
        task.pre_blocked_status = None
        task.save()
        log_change(task, "status", old_status, new_status, actor)
        return (True, None)

    # --- all other transitions must appear in the allow-list ---
    if (old_status, new_status) not in _ALLOWED:
        return (
            False,
            f"Moving a task from '{old_status}' to '{new_status}' is not "
            "permitted. Check the allowed status flow.",
        )

    # --- Done gate ---
    if new_status == S.DONE:
        # blocked_by entries whose blocking task is not yet done
        unfinished = task.blocked_by.exclude(
            blocking_task__status=S.DONE
        ).exists()
        if unfinished:
            return (
                False,
                "Cannot complete: this task is blocked by one or more "
                "unfinished tasks.",
            )

    # --- Blocked: snapshot current status ---
    if new_status == S.BLOCKED:
        task.pre_blocked_status = old_status

    task.status = new_status
    task.save()
    log_change(task, "status", old_status, new_status, actor)
    return (True, None)


def legal_next_statuses(task: Task) -> list[str]:
    """
    Return the status values that *attempt_transition* would accept right now.

    Used to determine which action buttons to render; does not perform any
    DB writes.
    """
    current = task.status

    if current == S.BLOCKED:
        if task.pre_blocked_status:
            return [task.pre_blocked_status]
        return []

    candidates = [to for (frm, to) in _ALLOWED if frm == current]

    if S.DONE in candidates:
        unfinished = task.blocked_by.exclude(
            blocking_task__status=S.DONE
        ).exists()
        if unfinished:
            candidates.remove(S.DONE)

    return candidates
