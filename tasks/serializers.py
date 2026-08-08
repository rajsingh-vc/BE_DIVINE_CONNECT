from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id", "task_code", "title", "description", "assignee",
            "due_date", "time", "priority", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "task_code", "created_at", "updated_at"]