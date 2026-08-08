from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, SystemSettingViewSet

router = DefaultRouter()
router.register(r"audit-logs", AuditLogViewSet, basename="audit-log")
router.register(r"settings", SystemSettingViewSet, basename="system-setting")

urlpatterns = router.urls
