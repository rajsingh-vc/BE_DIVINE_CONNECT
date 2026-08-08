from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AlertViewSet,
    LiveDarshanViewSet,
    LiveFestivalInfoViewSet,
    dashboard_stats,
    live_darshan_status,
    revenue_mix,
    visitor_flow,
)

router = DefaultRouter()
router.register(r"festival-info", LiveFestivalInfoViewSet, basename="live-festival-info")
router.register(r"alerts", AlertViewSet, basename="alert")
router.register(r"live-darshan-admin", LiveDarshanViewSet, basename="live-darshan-admin")

urlpatterns = [
    path("stats/", dashboard_stats, name="dashboard-stats"),
    path("visitor-flow/", visitor_flow, name="dashboard-visitor-flow"),
    path("revenue-mix/", revenue_mix, name="dashboard-revenue-mix"),
    path("live-darshan/", live_darshan_status, name="dashboard-live-darshan-status"),
] + router.urls