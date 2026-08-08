# crowd_status/apps.py — unchanged, included for confirmation only
from django.apps import AppConfig


class CrowdStatusConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crowd_status"
    verbose_name = "Crowd Status"

    def ready(self):
        from . import signals  # noqa: F401