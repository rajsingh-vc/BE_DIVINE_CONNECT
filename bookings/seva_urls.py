from rest_framework.routers import DefaultRouter

from .views import SevaViewSet

router = DefaultRouter()
router.register(r"", SevaViewSet, basename="seva")

urlpatterns = router.urls
