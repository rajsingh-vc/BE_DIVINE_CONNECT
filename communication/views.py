from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Announcement
from .serializers import AnnouncementSerializer


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["channel"]
    search_fields = ["title", "message"]
    ordering_fields = ["created_at"]
