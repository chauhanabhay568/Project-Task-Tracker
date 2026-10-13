from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import User


def manager_required(view_func):
    # Hiding a button in a template only hides it visually — this blocks the
    # view itself, so a Member can't reach it by hitting the URL directly.
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.MANAGER:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
