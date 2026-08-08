from django.contrib import admin

from .models import AuditLog, SystemSetting

admin.site.register(AuditLog)
admin.site.register(SystemSetting)
