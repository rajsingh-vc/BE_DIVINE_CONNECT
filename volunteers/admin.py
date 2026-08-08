from django.contrib import admin
from .models import Volunteer, Verification, VolunteerApproval, Notification, AuditLog


from django.contrib import admin
from .models import Volunteer, Verification, VolunteerApproval, Notification, AuditLog, Duty
# (add Duty to whatever import line already exists)


@admin.register(Duty)
class DutyAdmin(admin.ModelAdmin):
    list_display = ["duty_code", "title", "volunteer", "duty_date", "time", "priority", "status"]
    list_filter = ["status", "priority", "duty_date"]
    search_fields = ["duty_code", "title", "volunteer__name"]


admin.site.register(Volunteer)
admin.site.register(Verification)
admin.site.register(VolunteerApproval)
admin.site.register(Notification)
admin.site.register(AuditLog)