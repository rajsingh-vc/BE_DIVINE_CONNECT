from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, MealBookingViewSet, ScanBookingQRView

router = DefaultRouter()
router.register(r"", BookingViewSet, basename="booking")
router.register(r"meal-bookings", MealBookingViewSet, basename="meal-booking")

urlpatterns = router.urls + [
    path("scan-booking-qr/", ScanBookingQRView.as_view(), name="scan-booking-qr"),
]