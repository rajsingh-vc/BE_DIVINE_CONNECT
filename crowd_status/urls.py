# crowd_status/urls.py — FULL FILE
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminCrowdStatusViewSet,
    AttendanceListView,
    CrowdThresholdsView,
    DevoteeMyQRView,
    DevoteeSearchView,
    ManualCheckinView,
    ManualCounterAdminListView,
    ManualCounterView,
    MyAreaCrowdStatusView,
    ScanHistoryListView,
    ScanQRView,
    VerifyVolunteerView,
    VolunteerCrowdStatusView,
    VolunteerMyQRView,
)

router = DefaultRouter()
router.register(r"admin/crowd-status", AdminCrowdStatusViewSet, basename="admin-crowd-status")

urlpatterns = [
    # ---- QR attendance system ----
    path("scan-qr/", ScanQRView.as_view(), name="scan-qr"),
    path("verify-volunteer/", VerifyVolunteerView.as_view(), name="verify-volunteer"),
    path("manual-checkin/", ManualCheckinView.as_view(), name="manual-checkin"),
    path("devotees/search/", DevoteeSearchView.as_view(), name="devotee-search"),
    path("devotees/me/qr-data/", DevoteeMyQRView.as_view(), name="devotee-my-qr"),
    path("volunteers/me/qr-data/", VolunteerMyQRView.as_view(), name="volunteer-my-qr"),
    path("attendance/", AttendanceListView.as_view(), name="attendance-list"),
    path("scan-history/", ScanHistoryListView.as_view(), name="scan-history-list"),

    # ---- Crowd-density dashboard (separate feature) ----
    path("crowd-status/", VolunteerCrowdStatusView.as_view(), name="crowd-status-submit"),
    path("crowd-status/my-area/", MyAreaCrowdStatusView.as_view(), name="crowd-status-my-area"),
    path("admin/crowd-thresholds/", CrowdThresholdsView.as_view(), name="crowd-thresholds"),

    # ---- Manual Counter (volunteer +/- entries not captured via QR) ----
    path("manual-counter/", ManualCounterView.as_view(), name="manual-counter"),
    path("manual-counter/admin/", ManualCounterAdminListView.as_view(), name="manual-counter-admin"),

    path("", include(router.urls)),
]