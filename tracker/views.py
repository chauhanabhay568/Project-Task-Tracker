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
from .services import active_alerts_for_user, assign_user_to_task, cascade_unassign, dashboard_stats, filtered_task_queryset, set_due_date, sync_blockers
from .mixins import ProjectAccessMixin
from .models import AlertDismissal, Comment, Project, ProjectMembership, Task, TaskAssignment, User
from .transitions import attempt_transition, legal_next_statuses


class EmailLoginForm(forms.Form):
    # USERNAME_FIELD is left as 'username', but every account's username is set
    # equal to their email address at creation time, so presenting this field as
    # "Email" works without a custom auth backend.
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "class": "form-input"}),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )

    def get_credentials(self):
        # Returns {"username": ..., "password": ...} because Django's auth
        # system expects "username", not "email".
        return {
            "username": self.cleaned_data["email"],
            "password": self.cleaned_data["password"],
        }


class EmailLoginView(LoginView):
    template_name = "tracker/login.html"
    authentication_form = None

    def get_form(self, form_class=None):
        kwargs = self.get_form_kwargs()
        kwargs.pop("request", None)
        return EmailLoginForm(**kwargs)

    def form_valid(self, form):
        from django.contrib.auth import authenticate, login
        credentials = form.get_credentials()
        user = authenticate(self.request, **credentials)
        if user is None:
            form.add_error(None, "Invalid email or password.")
            return self.form_invalid(form)
        login(self.request, user)
        return super(LoginView, self).form_valid(form)


class ProjectListView(LoginRequiredMixin, ListView):
    template_name = "tracker/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        user = self.request.user
        if user.role == User.Role.MANAGER:
            return Project.objects.filter(archived=False).order_by("name")
        # Members only see projects they belong to — get their project IDs from
        # ProjectMembership, then filter Project to that set.
        member_project_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
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


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["key", "name", "description"]
        widgets = {
            "key": forms.TextInput(attrs={"class": "form-input"}),
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 4}),
        }


@method_decorator(manager_required, name="dispatch")
class ProjectCreateView(CreateView):
    form_class = ProjectForm
    template_name = "tracker/project_form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("project_detail", kwargs={"pk": self.object.pk})


@method_decorator(manager_required, name="dispatch")
class ProjectUpdateView(UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "tracker/project_form.html"

    def get_success_url(self):
        return reverse_lazy("project_detail", kwargs={"pk": self.object.pk})


# @require_POST ensures these can only be triggered by a form button, not a GET request.
# project.save() without update_fields touches all fields — acceptable here since
# archive/restore is the only write path for this flag.
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


@method_decorator(manager_required, name="dispatch")
class ArchivedProjectListView(ListView):
    template_name = "tracker/project_archived_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.filter(archived=True).order_by("name")


# ---------------------------------------------------------------------------
# Task views
# ---------------------------------------------------------------------------

class TaskForm(forms.ModelForm):
    blocking_tasks = forms.ModelMultipleChoiceField(
        queryset=Task.objects.none(),
        required=False,
        label="Blocked by",
        widget=forms.SelectMultiple(attrs={"class": "form-input"}),
    )

    class Meta:
        model = Task
        fields = ["title", "description", "priority", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "priority": forms.Select(attrs={"class": "form-input"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            qs = Task.objects.filter(project=project)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
                self.fields["blocking_tasks"].initial = (
                    self.instance.blocked_by.values_list("blocking_task", flat=True)
                )
            self.fields["blocking_tasks"].queryset = qs


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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def form_valid(self, form):
        form.instance.project = self.project
        form.instance.status = Task.Status.BACKLOG
        form.instance.save()
        self.object = form.instance
        sync_blockers(self.object, form.cleaned_data["blocking_tasks"])
        return redirect(self.get_success_url())

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
        ok, msg = assign_user_to_task(self.task, user, actor=request.user)
        if not ok:
            messages.error(request, msg)
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.project
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        sync_blockers(self.object, form.cleaned_data["blocking_tasks"])
        return redirect(self.get_success_url())

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


class AlertListView(LoginRequiredMixin, ListView):
    template_name = "tracker/alerts.html"
    context_object_name = "alerts"

    def get_queryset(self):
        return active_alerts_for_user(self.request.user).select_related("project")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from datetime import date
        ctx["today"] = date.today()
        return ctx


class TaskCsvExportView(LoginRequiredMixin, View):
    def get(self, request):
        import csv
        from django.http import StreamingHttpResponse

        qs = filtered_task_queryset(request.user, request.GET).prefetch_related("assignments__user")

        def rows():
            yield ["Title", "Project", "Status", "Priority", "Due Date", "Assignees"]
            for task in qs:
                assignees = ", ".join(a.user.username for a in task.assignments.all())
                yield [
                    task.title,
                    task.project.name,
                    task.get_status_display(),
                    task.get_priority_display(),
                    task.due_date or "",
                    assignees,
                ]

        class Echo:
            def write(self, value):
                return value

        writer = csv.writer(Echo())
        response = StreamingHttpResponse(
            (writer.writerow(row) for row in rows()),
            content_type="text/csv",
        )
        response["Content-Disposition"] = 'attachment; filename="tasks.csv"'
        return response


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        from django.shortcuts import render
        stats = dashboard_stats(request.user)
        return render(request, "tracker/dashboard.html", stats)


class DismissAlertView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        dismissal, _ = AlertDismissal.objects.get_or_create(
            task=task, user=request.user,
            defaults={"due_date_at_dismissal": task.due_date},
        )
        # Always refresh the snapshot so a stale dismissal is re-armed correctly.
        if dismissal.due_date_at_dismissal != task.due_date:
            dismissal.due_date_at_dismissal = task.due_date
            dismissal.save(update_fields=["due_date_at_dismissal"])
        return redirect("alert_list")
