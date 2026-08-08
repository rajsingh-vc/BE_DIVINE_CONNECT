from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Event, Visitor
from .serializers import EventSerializer, VisitorSerializer


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "event_code"]
    ordering_fields = ["date"]


class VisitorViewSet(viewsets.ModelViewSet):
    queryset = Visitor.objects.all()
    serializer_class = VisitorSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "zone"]
    search_fields = ["name", "visitor_code"]
    ordering_fields = ["check_in"]
