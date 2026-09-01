from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import User

"""
manager_required is a decorator that blocks non-managers from running a view — server-side, 
no matter how they try to access it.

How it works, in short:

- First checks the user is logged in at all (@login_required) — if not, redirects to login.
- Then checks request.user.role != User.Role.MANAGER — if they're not a manager, raises 
PermissionDenied (403 error), and the real view never runs.
- If they pass both checks, it calls the actual view function normally.

- Why it matters: hiding a button in a template only hides it visually — a Member could still 
hit the URL directly.

"""
def manager_required(view_func):
    # wrappers wraps another function to add extra behavior, without changing the original function's code.
    @wraps(view_func)
    # if you are not logged in then -  redirect to /login/ (handled by Django's built-in login_required)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.MANAGER:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
