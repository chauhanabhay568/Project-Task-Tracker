from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AlertDismissal,
    Comment,
    HistoryEntry,
    Project,
    ProjectMembership,
    Task,
    TaskAssignment,
    TaskBlocker,
    User,
)

admin.site.register(User, UserAdmin)
admin.site.register(Project)
admin.site.register(ProjectMembership)
admin.site.register(Task)
admin.site.register(TaskAssignment)
admin.site.register(TaskBlocker)
admin.site.register(HistoryEntry)
admin.site.register(Comment)
admin.site.register(AlertDismissal)
