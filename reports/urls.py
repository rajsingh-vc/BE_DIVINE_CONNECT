from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import SavedReportViewSet, summary_report

router = DefaultRouter()
router.register(r"saved", SavedReportViewSet, basename="saved-report")

urlpatterns = [
    path("summary/", summary_report, name="reports-summary"),
] + router.urls
