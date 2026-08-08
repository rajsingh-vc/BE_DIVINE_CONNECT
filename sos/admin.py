from django.contrib import admin

from .models import SOSAlert


@admin.register(SOSAlert)
class SOSAlertAdmin(admin.ModelAdmin):
    list_display = ("sos_code", "alert_type", "status", "location", "raised_by", "created_at")
    list_filter = ("alert_type", "status")
    search_fields = ("sos_code", "description", "location")
    readonly_fields = ("sos_code", "created_at", "updated_at")