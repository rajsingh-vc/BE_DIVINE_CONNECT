from rest_framework.routers import DefaultRouter

from .views import DevoteeViewSet

router = DefaultRouter()
router.register(r"", DevoteeViewSet, basename="devotee")

urlpatterns = router.urls
