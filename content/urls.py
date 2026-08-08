from rest_framework.routers import DefaultRouter

from .models import TempleInfo

from .views import (
    ContentPageViewSet,
    AnnouncementViewSet,
    GalleryItemViewSet,
    FAQViewSet,
    TempleInfoViewSet,
)
from .views import NewsPostViewSet
from .views import VideoItemViewSet

router = DefaultRouter()
router.register(r"pages", ContentPageViewSet, basename="content-page")
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"gallery", GalleryItemViewSet, basename="gallery")
router.register(r"faqs", FAQViewSet, basename="faq")
router.register(r"news", NewsPostViewSet, basename="news")
router.register(r"temple-info", TempleInfoViewSet, basename="temple-info")
router.register(r"videos", VideoItemViewSet, basename="video")

urlpatterns = router.urls