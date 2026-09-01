from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    ArchivedProjectListView,
    EmailLoginView,
    ProjectCreateView,
    ProjectDetailView,
    ProjectListView,
    ProjectUpdateView,
    TaskCreateView,
    TaskDeleteView,
    TaskDetailView,
    TaskUpdateView,
    archive_project,
    restore_project,
)

"""
path("login/", EmailLoginView.as_view(), name="login")
- "login/" — when someone visits /login/
- EmailLoginView.as_view() — run this view. .as_view() is required because EmailLoginView 
is a class, and Django expects a function. .as_view() converts it.
- name="login" — gives this URL a nickname so you can refer to it in templates or 
code as "login" instead of hardcoding /login/

path("logout/", LogoutView.as_view(), name="logout")
- Same idea — visiting /logout/ triggers Django's built-in logout logic

One-liner summary: This file defines two URLs — /login/ handled by your custom view, /logout/ 
handled by Django's built-in view — and gives each a name for easy reference elsewhere.

"""
urlpatterns = [
    path("login/", EmailLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("projects/", ProjectListView.as_view(), name="project_list"),
    path("projects/new/", ProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:pk>/edit/", ProjectUpdateView.as_view(), name="project_edit"),
    path("projects/<int:pk>/archive/", archive_project, name="project_archive"),
    path("projects/<int:pk>/restore/", restore_project, name="project_restore"),
    path("projects/archived/", ArchivedProjectListView.as_view(), name="project_archived_list"),
    path("projects/<int:project_pk>/tasks/new/", TaskCreateView.as_view(), name="task_create"),
    path("tasks/<int:pk>/", TaskDetailView.as_view(), name="task_detail"),
    path("tasks/<int:pk>/edit/", TaskUpdateView.as_view(), name="task_edit"),
    path("tasks/<int:pk>/delete/", TaskDeleteView.as_view(), name="task_delete"),
]
