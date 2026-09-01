"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path





"""
urlpatterns is just a Python list. Django reads this list to know which URL goes where.
---
path("admin/", admin.site.urls)
When someone visits yoursite.com/admin/, Django sends them to the built-in admin panel. admin.site.urls is provided by Django itself — you don't write it.
---
path("", include("tracker.urls"))

- "" means "match everything else" (no prefix)
- include("tracker.urls") means "go look inside tracker/urls.py for more URL patterns"

So this line says: for all other URLs, check tracker/urls.py to find the right view.

---
In simple terms:

Think of it like a receptionist:
- If the request starts with /admin/ → send to admin desk
- Everything else → forward to the tracker department, which has its own routing list

This URL is of main project and 

"""
urlpatterns = [
    path("admin/", admin.site.urls),
    # means go the urls.py file inside tracker
    path("", include("tracker.urls")),
]
