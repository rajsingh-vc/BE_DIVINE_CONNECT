from rest_framework.routers import DefaultRouter

from .views import DonationViewSet

router = DefaultRouter()
router.register(r"", DonationViewSet, basename="donation")

urlpatterns = router.urls
