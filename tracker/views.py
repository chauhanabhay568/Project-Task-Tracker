from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .audit import log_change
from .decorators import manager_required
from .services import cascade_unassign, filtered_task_queryset
from .mixins import ProjectAccessMixin
from .models import Comment, Project, ProjectMembership, Task, TaskAssignment, User
from .transitions import attempt_transition, legal_next_statuses


class EmailLoginForm(forms.Form):
    # Simplification: USERNAME_FIELD is left as 'username', but every account's
    # username is set equal to their email address at creation time, so presenting
    # this field as "Email" works without any custom auth backend.
    email = forms.EmailField(
        label="Email", # This is the human-readable text shown next to the input in the template. 
                        #Remember {{ form.email.label }} in your login.html? This is exactly where "Email" comes from.
        widget=forms.EmailInput(attrs={"autofocus": True, "class": "form-input"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )


    """
    This is a helper method. After the form is submitted and validated, cleaned_data holds the sanitized values. 
    It returns them as a dict with key "username" (not "email") because Django's auth system expects username.
    
    """
    def get_credentials(self):
        return {
            "username": self.cleaned_data["email"],
            "password": self.cleaned_data["password"],
        }


class EmailLoginView(LoginView):
    template_name = "tracker/login.html"
    authentication_form = None  # use default ModelBackend under the hood

    def get_form(self, form_class=None):
        kwargs = self.get_form_kwargs()
        kwargs.pop("request", None)
        # **kwargs means unpacking the dictionary
        # calling a class = creating an instance. The ** just unpacks the dict into named arguments
        return EmailLoginForm(**kwargs)


    def form_valid(self, form):

        """
        Purpose: runs once the submitted form passes validation — 
        checks credentials are actually correct, then logs the user in 
        or shows an error.
        If the form is not valid then renderinf happens automatically by Django else it redirects to /project/
        """
        from django.contrib.auth import authenticate, login
        # form.get_credentials() which returns {"username": email_value, "password": password_value}
        credentials = form.get_credentials()
        user = authenticate(self.request, **credentials)
        if user is None:
            form.add_error(None, "Invalid email or password.")
            return self.form_invalid(form)
        login(self.request, user)
        return super(LoginView, self).form_valid(form)

class ProjectListView(LoginRequiredMixin, ListView):
    template_name = "tracker/project_list.html" #tells ListView which template file to render.
    context_object_name = "projects" #Decides what variable name the template will use to access the list of objects.

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.MANAGER:
            return Project.objects.filter(archived=False).order_by("name")
        """
        first, look up every row in ProjectMembership where user matches this person — these rows 
        represent "this user belongs to this project." .values_list("project_id", flat=True) 
        extracts just the project IDs from those rows, as a flat list of numbers (rather than full objects) — e.g. [2, 5, 9]
        """
        member_project_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
        # Return only the projects whose id is in that list of member project IDs 
        # (and still excluding archived ones), sorted by name.
        return Project.objects.filter(archived=False, id__in=member_project_ids).order_by("name")


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "tracker/project_detail.html"
    context_object_name = "project"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        member_ids = self.object.memberships.values_list("user_id", flat=True)
        ctx["non_members"] = User.objects.exclude(pk__in=member_ids).order_by("username")
        return ctx

"""
a form for creating/editing a Project — but unlike forms.Form, a ModelForm builds 
its fields directly from a model, instead of you declaring each field by hand.
"""
class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["key", "name", "description"]
        widgets = {
            "key": forms.TextInput(attrs={"class": "form-input"}),
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
        }

"""
the "create a new project" page — shows the form, and on valid submission, creates a new Project row.
"""
@method_decorator(manager_required, name="dispatch")
class ProjectCreateView(CreateView):
    form_class = ProjectForm
    template_name = "tracker/project_form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

# builds the URL /projects/<pk>/ from the URL name instead of hardcoding the path.
    def get_success_url(self):
        return reverse_lazy("project_detail", kwargs={"pk": self.object.pk})

"""
the "edit an existing project" page — same form, but pre-filled with an existing project's data, 
and saves changes to that same row instead of creating a new one.
"""
@method_decorator(manager_required, name="dispatch")
class ProjectUpdateView(UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "tracker/project_form.html"

    def get_success_url(self):
        return reverse_lazy("project_detail", kwargs={"pk": self.object.pk})




"""
Both views do the same thing in opposite directions:

- @require_POST — only accepts POST requests (from a form button), not someone typing the URL
- @manager_required — only managers can reach this, members get 403
- get_object_or_404 — finds the project or returns 404
- Sets archived = True (or False for restore) and saves — only this one field, nothing else is touched
- Redirects back to the same project's detail page

"""
@require_POST
@manager_required
def archive_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project.archived = True
    project.save()
    return redirect("project_detail", pk=pk)


@require_POST
@manager_required
def restore_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project.archived = False
    project.save()
    return redirect("project_detail", pk=pk)


@require_POST
@manager_required
def add_member(request, pk):
    project = get_object_or_404(Project, pk=pk)
    user_id = request.POST.get("user_id")
    user = get_object_or_404(User, pk=user_id)
    ProjectMembership.objects.get_or_create(project=project, user=user)
    return redirect("project_detail", pk=pk)


@require_POST
@manager_required
def remove_member(request, pk, user_id):
    project = get_object_or_404(Project, pk=pk)
    user = get_object_or_404(User, pk=user_id)
    ProjectMembership.objects.filter(project=project, user=user).delete()
    count = cascade_unassign(user, project, actor=request.user)
    if count > 0:
        messages.info(
            request,
            f"Removed {user} from the project and unassigned them from {count} task(s).",
        )
    return redirect("project_detail", pk=pk)

"""
 It's the page at /projects/archived/ that lists all archived projects — only visible to managers.
"""
@method_decorator(manager_required, name="dispatch")
class ArchivedProjectListView(ListView):
    template_name = "tracker/project_archived_list.html"
    #  context_object_name = "projects" — passes the list to the template 
    # as {{ projects }}, same variable name as the regular list so the template works the same way.
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.filter(archived=True).order_by("name")


# ---------------------------------------------------------------------------
# Task views
# ---------------------------------------------------------------------------

"""
It creates a form automatically using the model(basically table) fields.
"""
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "priority", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "priority"   : forms.Select(attrs={"class": "form-input"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "Leave a comment…"}),
        }


class TaskCreateView(LoginRequiredMixin, ProjectAccessMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = "tracker/task_form.html"

    """
    When it runs: only after the submitted form has already passed validation (title isn't empty, due_date is a real date, etc.) — 
        right before the object gets saved to the database.
    form.instance is the not-yet-saved Task object that Django built from the form data. The form itself only collects title, 
    description, priority, due_date (that's all TaskForm.Meta.fields lists) — it has no field for project or status, because 
    those shouldn't come from user input. So this method fills in the two missing pieces by hand:

            project → whatever project the URL pointed to (self.project, supplied by ProjectAccessMixin)
            status → always force it to BACKLOG, since every task should start there

    Then super().form_valid(form) hands control back to Django's normal CreateView, which actually calls form.save() and stores the row.
    """
    def form_valid(self, form):
        form.instance.project = self.project
        form.instance.status = Task.Status.BACKLOG
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("project_detail", kwargs={"pk": self.project.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        return ctx


class TaskDetailView(LoginRequiredMixin, ProjectAccessMixin, DetailView):
    model = Task
    template_name = "tracker/task_detail.html"
    context_object_name = "task"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        status_display = dict(Task.Status.choices)
        ctx["legal_statuses"] = [
            (s, status_display[s]) for s in legal_next_statuses(self.object)
        ]
        assigned_user_ids = self.object.assignments.values_list("user_id", flat=True)
        ctx["assignees"] = User.objects.filter(pk__in=assigned_user_ids)
        member_ids = self.project.memberships.values_list("user_id", flat=True)
        ctx["assignable_members"] = User.objects.filter(
            pk__in=member_ids
        ).exclude(pk__in=assigned_user_ids).order_by("username")
        ctx["comment_form"] = CommentForm()

        timeline = [
            {"type": "created", "timestamp": self.object.created_at, "label": "Task created."}
        ]
        for entry in self.object.history.select_related("changed_by"):
            timeline.append({
                "type": "history",
                "timestamp": entry.changed_at,
                "field_name": entry.field_name,
                "old_value": entry.old_value,
                "new_value": entry.new_value,
                "changed_by": entry.changed_by,
            })
        for comment in self.object.comments.select_related("author"):
            timeline.append({
                "type": "comment",
                "timestamp": comment.timestamp,
                "author": comment.author,
                "text": comment.text,
            })
        timeline.sort(key=lambda e: e["timestamp"])
        ctx["timeline"] = timeline
        return ctx


class TaskStatusChangeView(LoginRequiredMixin, ProjectAccessMixin, View):
    http_method_names = ["post"]

    def get_object(self):
        if not hasattr(self, "task"):
            self.task = get_object_or_404(Task, pk=self.kwargs["pk"])
        return self.task

    def post(self, request, pk):
        self.get_object()
        new_status = request.POST.get("new_status")
        ok, reason = attempt_transition(self.task, new_status, actor=request.user)
        if ok:
            messages.success(request, f"Moved to {self.task.get_status_display()}.")
        else:
            messages.error(request, reason)
        return redirect("task_detail", pk=self.task.pk)


class TaskAssignView(LoginRequiredMixin, ProjectAccessMixin, View):
    http_method_names = ["post"]

    def get_object(self):
        if not hasattr(self, "task"):
            self.task = get_object_or_404(Task, pk=self.kwargs["pk"])
        return self.task

    def post(self, request, pk):
        self.get_object()
        user = get_object_or_404(User, pk=request.POST.get("user_id"))
        is_member = ProjectMembership.objects.filter(
            project=self.project, user=user
        ).exists()
        if not is_member:
            messages.error(
                request,
                f"{user.username} is not a member of this project and cannot be assigned.",
            )
            return redirect("task_detail", pk=self.task.pk)
        assignment, created = TaskAssignment.objects.get_or_create(
            task=self.task, user=user
        )
        if created:
            log_change(self.task, "assignee", None, str(user), request.user)
        return redirect("task_detail", pk=self.task.pk)


class TaskUnassignView(LoginRequiredMixin, ProjectAccessMixin, View):
    http_method_names = ["post"]

    def get_object(self):
        if not hasattr(self, "task"):
            self.task = get_object_or_404(Task, pk=self.kwargs["pk"])
        return self.task

    def post(self, request, pk):
        self.get_object()
        user = get_object_or_404(User, pk=request.POST.get("user_id"))
        deleted, _ = TaskAssignment.objects.filter(
            task=self.task, user=user
        ).delete()
        if deleted:
            log_change(self.task, "assignee", str(user), None, request.user)
        return redirect("task_detail", pk=self.task.pk)


class AddCommentView(LoginRequiredMixin, ProjectAccessMixin, View):
    http_method_names = ["post"]

    def get_object(self):
        if not hasattr(self, "task"):
            self.task = get_object_or_404(Task, pk=self.kwargs["pk"])
        return self.task

    def post(self, request, pk):
        self.get_object()
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = self.task
            comment.author = request.user
            comment.save()
        return redirect("task_detail", pk=self.task.pk)


class TaskUpdateView(LoginRequiredMixin, ProjectAccessMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = "tracker/task_form.html"

    def get_success_url(self):
        return reverse_lazy("task_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        return ctx


@method_decorator(manager_required, name="dispatch")
class TaskDeleteView(DeleteView):
    model = Task
    template_name = "tracker/task_confirm_delete.html"
    context_object_name = "task"

    def get_success_url(self):
        return reverse_lazy("project_detail", kwargs={"pk": self.object.project.pk})


class MyTasksView(LoginRequiredMixin, ListView):
    model = Task
    template_name = "tracker/my_tasks.html"
    context_object_name = "tasks"

    def get_queryset(self):
        return (
            Task.objects.filter(assignments__user=self.request.user)
            .select_related("project")
            .distinct()
            .order_by("due_date")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from datetime import date
        ctx["today"] = date.today()
        return ctx


class TaskListView(LoginRequiredMixin, ListView):
    template_name = "tracker/task_list.html"
    context_object_name = "tasks"
    paginate_by = 25

    def get_queryset(self):
        return filtered_task_queryset(self.request.user, self.request.GET).prefetch_related("assignments__user")

    def get_context_data(self, **kwargs):
        from datetime import date
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.role == User.Role.MANAGER:
            projects = Project.objects.filter(archived=False).order_by("name")
        else:
            member_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
            projects = Project.objects.filter(archived=False, id__in=member_ids).order_by("name")
        ctx["projects"] = projects
        ctx["status_choices"] = Task.Status.choices
        ctx["priority_choices"] = Task.Priority.choices
        ctx["all_users"] = User.objects.order_by("username")
        ctx["params"] = self.request.GET
        ctx["today"] = date.today()
        return ctx
