# The dashboard is a read-only aggregation layer over other apps' models.
# Alert and LiveFestivalInfo are kept as lightweight models so ops staff can
# post live alerts / festival schedule info that shows up on the command
# centre without redeploying.
from django.db import models


# =====================================================================
# ADD to dashboard/models.py — do not remove Alert / LiveFestivalInfo,
# just append this below them.
# =====================================================================

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class LiveDarshan(models.Model):
    """Live Ganpati Darshan stream shown as a banner on every dashboard
    (Admin / Volunteer / Devotee). Admins manage entries from "Live
    Darshan Management"; everyone else only ever sees the read-only
    /api/dashboard/live-darshan/ status endpoint.
    """

    title = models.CharField(max_length=200, blank=True, default="Live Ganpati Darshan")
    description = models.TextField(blank=True, default="")
    live_url = models.URLField(max_length=500, help_text="YouTube Live, Vimeo Live, or any HTTPS stream URL.")
    banner_image = models.ImageField(upload_to="live_darshan/banners/", blank=True, null=True)

    # Made optional — this feature no longer requires a scheduled window.
    # Kept (not removed) since older records may still use them.
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)

    # Admin on/off switch — this is now the SOLE source of truth for
    # whether the banner shows, unless a record still has both
    # start_datetime and end_datetime set (legacy scheduled behavior).
    is_live = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="live_darshan_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_datetime", "-created_at"]

    def clean(self):
        if self.start_datetime and self.end_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError({"end_datetime": "End time must be after start time."})

    def save(self, *args, **kwargs):
        if not self.title or not self.title.strip():
            self.title = "Live Ganpati Darshan"
        super().save(*args, **kwargs)

    @property
    def is_within_window(self) -> bool:
        # No window set -> always "within window" (admin toggle decides).
        if not self.start_datetime or not self.end_datetime:
            return True
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime

    @property
    def effective_is_live(self) -> bool:
        """What devotees/volunteers actually see. True only when the
        admin has switched it on AND (if a window is set) the current
        time falls inside it."""
        return bool(self.is_live and self.is_within_window)

    def __str__(self):
        return f"{self.title} ({'LIVE' if self.effective_is_live else 'not live'})"


class Alert(models.Model):
    class Severity(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    alert_code = models.CharField(max_length=20, unique=True, editable=False)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    category = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.alert_code:
            last = Alert.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.alert_code = f"ALT-{2200 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.alert_code


class LiveFestivalInfo(models.Model):
    """Live festival schedule entries shown on the Command Dashboard —
    e.g. "Aarti" 6:00-6:30 AM, "VIP Darshan" 10:00-11:00 AM. Admins add /
    edit / remove these entries; every logged-in user can view them.
    """

    # Name of the event/slot, e.g. "Aarti", "VIP Darshan", "Annadanam".
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField(blank=True, default="")
    # Lets an admin hide a past/cancelled entry without deleting it.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.title} ({self.start_time:%d %b, %H:%M})"