# =====================================================================
# dashboard/admin.py — create this file if it doesn't exist yet, or
# append to it if it does.
# =====================================================================

from django.contrib import admin

from .models import Alert, LiveDarshan, LiveFestivalInfo

admin.site.register(Alert)
admin.site.register(LiveFestivalInfo)
@admin.register(LiveDarshan)
class LiveDarshanAdmin(admin.ModelAdmin):
    list_display = ("title", "is_live", "effective_is_live", "start_datetime", "end_datetime", "created_by")
    list_filter = ("is_live",)
    search_fields = ("title", "description", "live_url")
    readonly_fields = ("created_by", "created_at", "updated_at")

    @admin.display(boolean=True, description="Currently showing as live")
    def effective_is_live(self, obj):
        return obj.effective_is_live

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# Register these too if they aren't already registered elsewhere.
