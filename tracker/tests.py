from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .decorators import manager_required
from .models import HistoryEntry, Project, Task, TaskBlocker, User
from .transitions import attempt_transition


def _dummy_view(request):
    return HttpResponse("ok", status=200)


_protected_view = manager_required(_dummy_view)


class ManagerRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.manager = User.objects.create_user(
            username="mgr@example.com",
            password="pass",
            role=User.Role.MANAGER,
        )
        self.member = User.objects.create_user(
            username="mbr@example.com",
            password="pass",
            role=User.Role.MEMBER,
        )

    def test_anonymous_redirects_to_login(self):
        request = self.factory.get("/fake/")
        request.user = type("AnonymousUser", (), {"is_authenticated": False})()
        response = _protected_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_member_gets_403(self):
        self.client.force_login(self.member)
        request = self.factory.get("/fake/")
        request.user = self.member
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            _protected_view(request)

    def test_manager_gets_200(self):
        request = self.factory.get("/fake/")
        request.user = self.manager
        response = _protected_view(request)
        self.assertEqual(response.status_code, 200)


class TransitionTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="actor@example.com",
            password="pass",
            role=User.Role.MEMBER,
        )
        self.project = Project.objects.create(
            key="TST",
            name="Test Project",
            owner=self.actor,
        )

    def _task(self, status, pre_blocked_status=None):
        t = Task.objects.create(
            project=self.project,
            title="T",
            status=status,
        )
        if pre_blocked_status:
            t.pre_blocked_status = pre_blocked_status
            t.save()
        return t

    # ------------------------------------------------------------------ #
    # Basic forward flow                                                   #
    # ------------------------------------------------------------------ #

    def test_backlog_to_in_progress(self):
        task = self._task(Task.Status.BACKLOG)
        ok, msg = attempt_transition(task, Task.Status.IN_PROGRESS, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_PROGRESS)
        # audit entry written
        entry = HistoryEntry.objects.get(task=task, field_name="status")
        self.assertEqual(entry.old_value, Task.Status.BACKLOG)
        self.assertEqual(entry.new_value, Task.Status.IN_PROGRESS)
        self.assertEqual(entry.changed_by, self.actor)

    def test_in_progress_to_in_review(self):
        task = self._task(Task.Status.IN_PROGRESS)
        ok, msg = attempt_transition(task, Task.Status.IN_REVIEW, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_REVIEW)

    # ------------------------------------------------------------------ #
    # Blocked transitions                                                  #
    # ------------------------------------------------------------------ #

    def test_in_progress_to_blocked_saves_pre_blocked_status(self):
        task = self._task(Task.Status.IN_PROGRESS)
        ok, msg = attempt_transition(task, Task.Status.BLOCKED, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.BLOCKED)
        self.assertEqual(task.pre_blocked_status, Task.Status.IN_PROGRESS)

    def test_in_review_to_blocked_saves_pre_blocked_status(self):
        # separate task to prove the value comes from the task, not a constant
        task = self._task(Task.Status.IN_REVIEW)
        ok, msg = attempt_transition(task, Task.Status.BLOCKED, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.BLOCKED)
        self.assertEqual(task.pre_blocked_status, Task.Status.IN_REVIEW)

    def test_blocked_from_in_progress_unblocks_to_in_progress(self):
        task = self._task(Task.Status.BLOCKED, pre_blocked_status=Task.Status.IN_PROGRESS)
        ok, msg = attempt_transition(task, Task.Status.IN_PROGRESS, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_PROGRESS)
        self.assertIsNone(task.pre_blocked_status)
        # audit entry
        entry = HistoryEntry.objects.get(task=task, field_name="status")
        self.assertEqual(entry.old_value, Task.Status.BLOCKED)
        self.assertEqual(entry.new_value, Task.Status.IN_PROGRESS)
        self.assertEqual(entry.changed_by, self.actor)

    def test_blocked_from_in_review_unblocks_to_in_review(self):
        task = self._task(Task.Status.BLOCKED, pre_blocked_status=Task.Status.IN_REVIEW)
        ok, msg = attempt_transition(task, Task.Status.IN_REVIEW, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_REVIEW)
        self.assertIsNone(task.pre_blocked_status)

    def test_blocked_to_wrong_status_fails(self):
        task = self._task(Task.Status.BLOCKED, pre_blocked_status=Task.Status.IN_PROGRESS)
        ok, msg = attempt_transition(task, Task.Status.DONE, self.actor)
        self.assertFalse(ok)
        self.assertIsNotNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.BLOCKED)

    # ------------------------------------------------------------------ #
    # Done / reopen                                                        #
    # ------------------------------------------------------------------ #

    def test_done_to_in_progress_reopen(self):
        task = self._task(Task.Status.DONE)
        ok, msg = attempt_transition(task, Task.Status.IN_PROGRESS, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_PROGRESS)

    def test_backlog_to_done_fails(self):
        task = self._task(Task.Status.BACKLOG)
        ok, msg = attempt_transition(task, Task.Status.DONE, self.actor)
        self.assertFalse(ok)
        self.assertIsNotNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.BACKLOG)

    # ------------------------------------------------------------------ #
    # Blocker gate                                                         #
    # ------------------------------------------------------------------ #

    def test_done_blocked_by_unfinished_task_fails(self):
        blocker = self._task(Task.Status.IN_PROGRESS)
        blocked = self._task(Task.Status.IN_REVIEW)
        TaskBlocker.objects.create(blocked_task=blocked, blocking_task=blocker)

        ok, msg = attempt_transition(blocked, Task.Status.DONE, self.actor)
        self.assertFalse(ok)
        self.assertIn("blocked", msg.lower())
        blocked.refresh_from_db()
        self.assertEqual(blocked.status, Task.Status.IN_REVIEW)

    def test_done_allowed_once_blocker_is_done(self):
        blocker = self._task(Task.Status.IN_PROGRESS)
        blocked = self._task(Task.Status.IN_REVIEW)
        TaskBlocker.objects.create(blocked_task=blocked, blocking_task=blocker)

        blocker.status = Task.Status.DONE
        blocker.save()

        ok, msg = attempt_transition(blocked, Task.Status.DONE, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        blocked.refresh_from_db()
        self.assertEqual(blocked.status, Task.Status.DONE)
