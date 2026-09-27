"""Root URL configuration. Each app's API routes are mounted under /api/."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("common.urls")),
    path("api/", include("accounts.urls")),
    path("api/", include("vendors.urls")),
    path("api/", include("invoices.urls")),
    path("api/", include("audit.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("system_settings.urls")),
    path("api/", include("fraud.urls")),
    path("api/", include("approvals.urls")),
    path("api/", include("reports.urls")),
]
