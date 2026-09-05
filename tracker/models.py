from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        MEMBER = "member", "Member"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    def __str__(self):
        return self.username


class Project(models.Model):
    key = models.CharField(max_length=10, unique=True)  # e.g. "PROJ"
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_projects")
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.key}] {self.name}"


class ProjectMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "project")

    def __str__(self):
        return f"{self.user} → {self.project}"


class Task(models.Model):
    class Status(models.TextChoices):
        BACKLOG = "backlog", "Backlog"
        IN_PROGRESS = "in_progress", "In Progress"
        IN_REVIEW = "in_review", "In Review"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BACKLOG)
    # Stores the status that was active before a task became Blocked,
    # so it can be restored when the block is lifted.
    pre_blocked_status = models.CharField(
        max_length=20, choices=Status.choices, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.project.key}] {self.title}"


class TaskAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assignments")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "task")

    def __str__(self):
        return f"{self.user} → {self.task}"


class TaskBlocker(models.Model):
    # "blocked_task is blocked by blocking_task"
    blocked_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="blocked_by")
    blocking_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="blocks")

    class Meta:
        unique_together = ("blocked_task", "blocking_task")

    def __str__(self):
        return f"{self.blocking_task} blocks {self.blocked_task}"


class HistoryEntry(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="history")
    field_name = models.CharField(max_length=100)
    # Values are always stored as strings (coerced by log_change in audit.py).
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="history_entries")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.task} · {self.field_name} at {self.changed_at:%Y-%m-%d %H:%M}"


class Comment(models.Model):
    # Comments are append-only. No edit or delete views should ever be built.
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="comments")
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"


class AlertDismissal(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="alert_dismissals")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="alert_dismissals")
    dismissed_at = models.DateTimeField(auto_now_add=True)
    # Snapshot of the task's due date at dismissal time.
    # If the due date later changes, the alert reappears for this user.
    due_date_at_dismissal = models.DateField()

    class Meta:
        unique_together = ("task", "user")

    def __str__(self):
        return f"{self.user} dismissed alert for {self.task} on {self.dismissed_at:%Y-%m-%d}"
