from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Task
from .serializers import TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "priority"]
    search_fields = ["title", "task_code", "assignee"]
    ordering_fields = ["due_date", "created_at", "priority"]