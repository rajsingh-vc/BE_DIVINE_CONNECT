from rest_framework.routers import DefaultRouter

from .views import IncidentReportViewSet

router = DefaultRouter()
router.register(r"incidents", IncidentReportViewSet, basename="incident-report")

urlpatterns = router.urls