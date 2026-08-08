"""
Sansthan Divine Ops — root URL configuration.

All API endpoints are namespaced under /api/. Each app owns its own
urls.py; this file just wires them together.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from payments.views import health_check
from dashboard.views import live_darshan_status

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth (signup / login / forgot-password / JWT refresh)
    path("api/auth/", include("accounts.urls")),

    # Live Ganpati Darshan, aliased at the bare /api/ root as well as
    # under /api/dashboard/ — both hit the exact same config-driven view.
    path("api/live-darshan/", live_darshan_status, name="live-darshan-status-root"),

    # Feature modules
    path("api/dashboard/", include("dashboard.urls")),
    path("api/devotees/", include("devotees.urls")),
    path("api/volunteers/", include("volunteers.urls")),
    path("api/bookings/", include("bookings.urls")),
    path("api/sevas/", include("bookings.seva_urls")),
    path("api/bills/", include("bookings.bill_urls")),
    path("api/donations/", include("donations.urls")),
    path("api/events/", include("events.urls")),
    path("api/visitors/", include("events.visitor_urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/content/", include("content.urls")),
    path("api/reports/", include("reports.urls")),
    path("api/communication/", include("communication.urls")),
    path("api/platform-admin/", include("platform_admin.urls")),
    path("api/tasks/", include("tasks.urls")),
    path("api/incidents/", include("incidents.urls")),
    path("api/sos/", include("sos.urls")),
    path("payments/", include("payments.urls")),
    path("api/", include("crowd_status.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)