from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .decorators import manager_required
from .models import HistoryEntry, Project, ProjectMembership, Task, TaskBlocker, User
from .services import bulk_apply_action
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

    def test_backlog_to_in_progress(self):
        task = self._task(Task.Status.BACKLOG)
        ok, msg = attempt_transition(task, Task.Status.IN_PROGRESS, self.actor)
        self.assertTrue(ok)
        self.assertIsNone(msg)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_PROGRESS)
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


class BulkApplyActionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr@example.com", password="pass", role=User.Role.MANAGER,
        )
        self.member = User.objects.create_user(
            username="mbr@example.com", password="pass", role=User.Role.MEMBER,
        )
        self.outsider = User.objects.create_user(
            username="out@example.com", password="pass", role=User.Role.MEMBER,
        )
        self.project = Project.objects.create(key="TST", name="Test Project", owner=self.manager)
        ProjectMembership.objects.create(user=self.member, project=self.project)

    def _task(self, status=Task.Status.BACKLOG):
        return Task.objects.create(project=self.project, title="T", status=status)

    def test_status_change_reports_per_task_success_and_failure(self):
        ok_task = self._task(Task.Status.BACKLOG)
        bad_task = self._task(Task.Status.BACKLOG)  # Backlog -> Done is not a legal jump

        results = bulk_apply_action(
            self.manager,
            [ok_task.pk, bad_task.pk],
            "status",
            new_status=Task.Status.IN_PROGRESS,
        )

        by_id = {r["task_id"]: r for r in results}
        self.assertTrue(by_id[ok_task.pk]["ok"])
        ok_task.refresh_from_db()
        self.assertEqual(ok_task.status, Task.Status.IN_PROGRESS)

        results = bulk_apply_action(
            self.manager, [bad_task.pk], "status", new_status=Task.Status.DONE,
        )
        self.assertFalse(results[0]["ok"])
        self.assertIsNotNone(results[0]["message"])
        # bad_task legitimately moved to In Progress in the first call; the
        # second call's illegal In Progress -> Done jump must not move it further.
        bad_task.refresh_from_db()
        self.assertEqual(bad_task.status, Task.Status.IN_PROGRESS)

    def test_assignee_action_rejects_non_member(self):
        task = self._task()
        results = bulk_apply_action(
            self.manager, [task.pk], "assignee", assignee_id=self.outsider.pk,
        )
        self.assertFalse(results[0]["ok"])
        self.assertIn("not a member", results[0]["message"])

    def test_due_date_action_applies_and_logs(self):
        import datetime
        task = self._task()
        new_due = datetime.date.today() + datetime.timedelta(days=3)
        results = bulk_apply_action(self.manager, [task.pk], "due_date", due_date=new_due)
        self.assertTrue(results[0]["ok"])
        task.refresh_from_db()
        self.assertEqual(task.due_date, new_due)
        self.assertTrue(HistoryEntry.objects.filter(task=task, field_name="due_date").exists())

    def test_member_without_project_access_is_rejected_per_task(self):
        task = self._task()
        results = bulk_apply_action(
            self.outsider, [task.pk], "status", new_status=Task.Status.IN_PROGRESS,
        )
        self.assertFalse(results[0]["ok"])
        self.assertIn("access", results[0]["message"])
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.BACKLOG)

    def test_unknown_task_id_reported_without_failing_whole_batch(self):
        ok_task = self._task()
        results = bulk_apply_action(
            self.manager, [ok_task.pk, 999999], "status", new_status=Task.Status.IN_PROGRESS,
        )
        by_id = {r["task_id"]: r for r in results}
        self.assertTrue(by_id[ok_task.pk]["ok"])
        self.assertFalse(by_id[999999]["ok"])
        self.assertEqual(by_id[999999]["message"], "Task not found.")
