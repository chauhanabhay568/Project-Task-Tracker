from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Redirect from / so the app doesn't show a blank page on first load.
    path("", RedirectView.as_view(url="/projects/", permanent=False)),
    path("", include("tracker.urls")),
]
