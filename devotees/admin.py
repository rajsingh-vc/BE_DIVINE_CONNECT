from django.contrib import admin

from .models import Devotee


@admin.register(Devotee)
class DevoteeAdmin(admin.ModelAdmin):
    list_display = ("devotee_code", "full_name", "city", "tier", "visits", "total_donated")
    list_filter = ("tier", "city")
    search_fields = ("devotee_code", "full_name", "mobile")
