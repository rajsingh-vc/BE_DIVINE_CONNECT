from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "channel", "audience", "sent_at")
    list_filter = ("channel",)
    search_fields = ("title",)
