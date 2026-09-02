from django.core.exceptions import PermissionDenied

from .models import Project, ProjectMembership, User

# that checks if the logged-in user is a member or manager of the project before allowing access to task views
class ProjectAccessMixin:
    """
    Resolves the relevant project and enforces membership/manager access.
    Sets self.project for the view to use.
    """

    def dispatch(self, request, *args, **kwargs):
        if "project_pk" in kwargs:
            self.project = Project.objects.get(pk=kwargs["project_pk"])
        else:
            self.project = self.get_object().project

        user = request.user
        is_manager = user.role == User.Role.MANAGER
        is_member = ProjectMembership.objects.filter(user=user, project=self.project).exists()

        if not (is_manager or is_member):
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)
