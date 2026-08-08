from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    VolunteerViewSet,
    NotificationViewSet,
    DutyViewSet,
    MealSessionViewSet,
    MealScanView,
    MealSelfScanView,
    MealStatsView,
)

router = DefaultRouter()
router.register("volunteers", VolunteerViewSet, basename="volunteer")
router.register("notifications", NotificationViewSet, basename="volunteer-notification")
router.register("duties", DutyViewSet, basename="duty")
router.register("meals/sessions", MealSessionViewSet, basename="meal-sessions")

urlpatterns = [
    path("meals/scan/", MealScanView.as_view(), name="meal-scan"),
    path("meals/self-scan/", MealSelfScanView.as_view(), name="meal-self-scan"),
    path("meals/stats/", MealStatsView.as_view(), name="meal-stats"),
    *router.urls,
]