"""
Seed the database with demo data.

Run once against a fresh DB:
    python manage.py seed

Safe to re-run — exits early if users already exist.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.audit import log_change
from tracker.models import (
    AlertDismissal,
    Comment,
    Project,
    ProjectMembership,
    Task,
    TaskAssignment,
    TaskBlocker,
    User,
)


class Command(BaseCommand):
    help = "Seed demo users, projects, and tasks"

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write("Database already has users — skipping seed.")
            return

        today = date.today()

        # ── Users ──────────────────────────────────────────────────────────────
        alice = User.objects.create_user(
            username="alice@demo.com", email="alice@demo.com",
            password="demo1234", role=User.Role.MANAGER,
        )
        bob = User.objects.create_user(
            username="bob@demo.com", email="bob@demo.com",
            password="demo1234", role=User.Role.MANAGER,
        )
        carol = User.objects.create_user(
            username="carol@demo.com", email="carol@demo.com",
            password="demo1234", role=User.Role.MEMBER,
        )
        dave = User.objects.create_user(
            username="dave@demo.com", email="dave@demo.com",
            password="demo1234", role=User.Role.MEMBER,
        )
        eve = User.objects.create_user(
            username="eve@demo.com", email="eve@demo.com",
            password="demo1234", role=User.Role.MEMBER,
        )

        # ── Projects ───────────────────────────────────────────────────────────
        alpha = Project.objects.create(
            key="ALPHA", name="Alpha Platform",
            description="Core platform rebuild for the next generation product.",
            owner=alice,
        )
        beta = Project.objects.create(
            key="BETA", name="Beta Mobile App",
            description="Native mobile app for iOS and Android.",
            owner=bob,
        )
        gamma = Project.objects.create(
            key="GAMMA", name="Gamma Analytics",
            description="Internal analytics dashboard for business intelligence.",
            owner=alice,
        )
        # Archived project
        delta = Project.objects.create(
            key="DELTA", name="Delta Legacy Migration",
            description="Migrating legacy systems to the new infrastructure.",
            owner=bob, archived=True,
        )

        # ── Memberships ────────────────────────────────────────────────────────
        for project, members in [
            (alpha, [carol, dave, eve]),
            (beta,  [carol, eve]),
            (gamma, [dave]),
            (delta, [carol, dave]),
        ]:
            for member in members:
                ProjectMembership.objects.create(user=member, project=project)

        # ── Tasks ──────────────────────────────────────────────────────────────
        def task(project, title, status, priority, due_offset=None, description=""):
            due = (today + timedelta(days=due_offset)) if due_offset is not None else None
            return Task.objects.create(
                project=project, title=title, status=status,
                priority=priority, due_date=due, description=description,
            )

        S = Task.Status
        P = Task.Priority

        # Alpha tasks
        t1 = task(alpha, "Set up CI/CD pipeline",        S.DONE,        P.HIGH,     -30)
        t2 = task(alpha, "Design new auth flow",          S.DONE,        P.HIGH,     -20)
        t3 = task(alpha, "Implement OAuth integration",   S.IN_REVIEW,   P.HIGH,       5)
        t4 = task(alpha, "Write API documentation",       S.IN_PROGRESS, P.MEDIUM,    10)
        t5 = task(alpha, "Database schema migration",     S.IN_PROGRESS, P.CRITICAL,  -3,
                  "Migrate user table to new schema with role-based access.")
        t6 = task(alpha, "Performance profiling",         S.BACKLOG,     P.LOW,       20)
        t7 = task(alpha, "Security audit",                S.BACKLOG,     P.HIGH,      15)

        # t5 is blocked by t3
        t5.pre_blocked_status = S.IN_PROGRESS
        t5.status = S.BLOCKED
        t5.save()
        TaskBlocker.objects.create(blocked_task=t5, blocking_task=t3)

        # Beta tasks
        t8  = task(beta, "UI component library",         S.DONE,        P.MEDIUM,   -25)
        t9  = task(beta, "Push notification service",    S.IN_PROGRESS, P.HIGH,       7)
        t10 = task(beta, "Offline mode support",         S.BACKLOG,     P.MEDIUM,    30)
        t11 = task(beta, "App store submission",         S.BACKLOG,     P.CRITICAL,  45,
                   "Submit to both App Store and Google Play.")
        t12 = task(beta, "Beta testing with 50 users",  S.IN_REVIEW,   P.HIGH,      -2)
        t13 = task(beta, "Fix login crash on Android",  S.IN_PROGRESS, P.CRITICAL,  -5,
                   "Reproducible on Android 12+. Stack trace in Sentry issue #4421.")

        # t11 blocked by t12
        t11.pre_blocked_status = S.BACKLOG
        t11.status = S.BLOCKED
        t11.save()
        TaskBlocker.objects.create(blocked_task=t11, blocking_task=t12)

        # Gamma tasks
        t14 = task(gamma, "Data ingestion pipeline",    S.IN_PROGRESS, P.HIGH,      12)
        t15 = task(gamma, "Dashboard wireframes",       S.DONE,        P.MEDIUM,   -10)
        t16 = task(gamma, "Chart components",           S.IN_REVIEW,   P.MEDIUM,     8)
        t17 = task(gamma, "Export to CSV/PDF",          S.BACKLOG,     P.LOW,       25)
        t18 = task(gamma, "User permissions model",     S.IN_PROGRESS, P.HIGH,      -7,
                   "Define row-level permissions for report access.")

        # ── Assignments ────────────────────────────────────────────────────────
        assignments = [
            (t3, carol), (t3, dave),
            (t4, dave),
            (t5, carol),
            (t6, eve),
            (t9, eve),
            (t12, carol), (t13, carol),
            (t14, dave),
            (t16, dave),
            (t18, dave),
        ]
        for t, u in assignments:
            TaskAssignment.objects.create(task=t, user=u)

        # ── History entries ────────────────────────────────────────────────────
        # Simulate realistic field changes using log_change
        log_change(t1, "status", S.BACKLOG,      S.IN_PROGRESS, alice)
        log_change(t1, "status", S.IN_PROGRESS,  S.IN_REVIEW,   carol)
        log_change(t1, "status", S.IN_REVIEW,    S.DONE,        alice)

        log_change(t2, "status", S.BACKLOG,      S.IN_PROGRESS, alice)
        log_change(t2, "priority", P.MEDIUM,     P.HIGH,        alice)
        log_change(t2, "status", S.IN_PROGRESS,  S.IN_REVIEW,   dave)
        log_change(t2, "status", S.IN_REVIEW,    S.DONE,        alice)

        log_change(t5, "status", S.BACKLOG,      S.IN_PROGRESS, carol)
        log_change(t5, "status", S.IN_PROGRESS,  S.BLOCKED,     alice)

        log_change(t8, "status", S.BACKLOG,      S.IN_PROGRESS, eve)
        log_change(t8, "status", S.IN_PROGRESS,  S.IN_REVIEW,   bob)
        log_change(t8, "status", S.IN_REVIEW,    S.DONE,        bob)

        log_change(t13, "priority", P.HIGH,      P.CRITICAL,    bob)
        log_change(t13, "due_date", None,        today - timedelta(days=5), bob)

        log_change(t15, "status", S.BACKLOG,     S.IN_PROGRESS, dave)
        log_change(t15, "status", S.IN_PROGRESS, S.IN_REVIEW,   alice)
        log_change(t15, "status", S.IN_REVIEW,   S.DONE,        alice)

        log_change(t18, "status", S.BACKLOG,     S.IN_PROGRESS, dave)
        log_change(t18, "due_date", None,        today - timedelta(days=7), alice)

        # ── Comments ───────────────────────────────────────────────────────────
        Comment.objects.create(task=t3, author=carol,
            text="OAuth flow is working end-to-end in staging. Ready for review.")
        Comment.objects.create(task=t3, author=dave,
            text="Left a few inline comments on the token refresh logic — minor things.")
        Comment.objects.create(task=t3, author=alice,
            text="Looks good overall. Approving once the refresh issue is addressed.")

        Comment.objects.create(task=t5, author=carol,
            text="Blocked on t3 merging first — migration script is ready to go otherwise.")

        Comment.objects.create(task=t13, author=carol,
            text="Confirmed on Pixel 6 running Android 12. Happens every time on cold start.")
        Comment.objects.create(task=t13, author=bob,
            text="Looks like a race condition in the splash screen. Investigating.")

        Comment.objects.create(task=t18, author=dave,
            text="Permissions model drafted. Waiting on Alice to review before we proceed.")

        # ── Alert dismissal (eve dismisses one overdue alert) ──────────────────
        # t13 is overdue and assigned to carol — let carol dismiss it
        if t13.due_date and t13.due_date < today:
            AlertDismissal.objects.create(
                task=t13, user=carol,
                due_date_at_dismissal=t13.due_date,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {User.objects.count()} users, "
            f"{Project.objects.count()} projects ({Project.objects.filter(archived=True).count()} archived), "
            f"{Task.objects.count()} tasks"
        ))
