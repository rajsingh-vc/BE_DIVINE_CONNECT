from django.contrib import admin

from .models import IncidentReport


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ("incident_code", "title", "category", "severity", "status", "reported_by", "created_at")
    list_filter = ("category", "severity", "status")
    search_fields = ("incident_code", "title", "description")