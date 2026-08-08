from django.contrib import admin

from .models import Event, Visitor


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("event_code", "name", "date", "status")
    list_filter = ("status",)
    search_fields = ("name", "event_code")


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("visitor_code", "name", "zone", "status", "check_in")
    list_filter = ("status", "zone")
    search_fields = ("name", "visitor_code")
