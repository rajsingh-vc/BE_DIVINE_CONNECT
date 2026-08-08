from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "full_name", "user_type", "is_active", "date_joined")
    list_filter = ("user_type", "is_active", "is_staff")
    search_fields = ("username", "email", "full_name")
    fieldsets = UserAdmin.fieldsets + (
        ("Sansthan Info", {"fields": ("full_name", "user_type", "phone")}),
    )
