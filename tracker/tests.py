from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .decorators import manager_required
from .models import User


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
