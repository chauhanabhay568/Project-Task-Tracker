from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import EmailLoginView, ProjectCreateView, ProjectDetailView, ProjectListView, ProjectUpdateView

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
]
