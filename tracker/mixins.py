from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Project, ProjectMembership, User

# that checks if the logged-in user is a member or manager of the project before allowing access to task views
class ProjectAccessMixin:
    """
    Resolves the relevant project and enforces membership/manager access.
    Sets self.project for the view to use.
    """

    def get_project(self, **kwargs):
        # Task views carry the project in the URL; project views resolve it from
        # the object itself, which for a Project view *is* the project.
        if "project_pk" in kwargs:
            return get_object_or_404(Project, pk=kwargs["project_pk"])
        obj = self.get_object()
        return obj if isinstance(obj, Project) else obj.project

    def dispatch(self, request, *args, **kwargs):
        self.project = self.get_project(**kwargs)

        user = request.user
        is_manager = user.role == User.Role.MANAGER
        is_member = ProjectMembership.objects.filter(user=user, project=self.project).exists()

        if not (is_manager or is_member):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)
