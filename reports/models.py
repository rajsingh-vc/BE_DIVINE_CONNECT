# Reports are generated on the fly from other apps' data (see views.py).
# No dedicated models are required beyond an optional saved-report log.
from django.conf import settings
from django.db import models


class SavedReport(models.Model):
    name = models.CharField(max_length=150)
    report_type = models.CharField(max_length=50)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    parameters = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return self.name
