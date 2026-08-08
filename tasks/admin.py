from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["task_code", "title", "assignee", "priority", "status", "due_date"]
    list_filter = ["status", "priority"]
    search_fields = ["task_code", "title", "assignee"]