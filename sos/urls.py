from rest_framework.routers import DefaultRouter

from .views import SOSAlertViewSet

router = DefaultRouter()
router.register(r"alerts", SOSAlertViewSet, basename="sos-alert")

urlpatterns = router.urls