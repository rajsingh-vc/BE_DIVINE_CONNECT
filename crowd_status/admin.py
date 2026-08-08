# crowd_status/admin.py — FULL FILE
from django.contrib import admin



from .models import Attendance, CrowdStatus, CrowdThresholds, ScanHistory, VolunteerAreaAssignment

from django.contrib import admin
from .models import ManualCounter

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("devotee", "check_type", "scan_method", "volunteer", "timestamp", "status")
    list_filter = ("check_type", "scan_method", "status")
    search_fields = ("devotee__full_name", "devotee__devotee_code", "booking_reference")
    date_hierarchy = "timestamp"


@admin.register(ScanHistory)
class ScanHistoryAdmin(admin.ModelAdmin):
    list_display = ("user_type", "devotee", "volunteer", "scan_method", "action_type", "scan_status", "scan_time")
    list_filter = ("user_type", "scan_method", "scan_status")
    search_fields = ("devotee__full_name", "volunteer__username", "booking_reference")
    date_hierarchy = "scan_time"


@admin.register(CrowdStatus)
class CrowdStatusAdmin(admin.ModelAdmin):
    list_display = ("assigned_area", "crowd_level", "approx_visitors", "wait_time", "updated_by", "timestamp", "status")
    list_filter = ("crowd_level", "status")
    search_fields = ("assigned_area",)


@admin.register(VolunteerAreaAssignment)
class VolunteerAreaAssignmentAdmin(admin.ModelAdmin):
    list_display = ("volunteer", "assigned_area")
    search_fields = ("volunteer__username", "assigned_area")


@admin.register(CrowdThresholds)
class CrowdThresholdsAdmin(admin.ModelAdmin):
    list_display = ("low_max", "moderate_max")

    def has_add_permission(self, request):
        # Singleton — only allow editing the one row created by CrowdThresholds.load()
        return not CrowdThresholds.objects.exists()





@admin.register(ManualCounter)
class ManualCounterAdmin(admin.ModelAdmin):
    list_display = ["id", "volunteer", "assigned_area", "action", "count", "reason", "timestamp"]
    list_filter = ["assigned_area", "action", "timestamp"]
    search_fields = ["assigned_area", "reason", "volunteer__username", "volunteer__first_name", "volunteer__last_name"]
    readonly_fields = [f.name for f in ManualCounter._meta.fields]
    ordering = ["-timestamp"]