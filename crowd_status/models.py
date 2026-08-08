# crowd_status/models.py — FULL FILE
from django.conf import settings
from django.db import models
from django.utils import timezone
# --- add near the top, if not already there ---
from django.db.models import Sum, Q as DBQ  # Sum/Q used by ManualCounter aggregates

# from .models import Attendance, CrowdStatus, CrowdThresholds, MealCollection, ScanHistory, VolunteerAreaAssignment


class Attendance(models.Model):
    CHECK_IN, CHECK_OUT = "CHECK_IN", "CHECK_OUT"
    CHECK_TYPE_CHOICES = [(CHECK_IN, "Check In"), (CHECK_OUT, "Check Out")]
    QR, MANUAL = "QR", "MANUAL"
    SCAN_METHOD_CHOICES = [(QR, "QR"), (MANUAL, "Manual")]
    SUCCESS, FAILED = "SUCCESS", "FAILED"
    STATUS_CHOICES = [(SUCCESS, "Success"), (FAILED, "Failed")]

    devotee = models.ForeignKey("devotees.Devotee", on_delete=models.CASCADE, related_name="attendances")
    volunteer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_recorded")
    check_type = models.CharField(max_length=10, choices=CHECK_TYPE_CHOICES)
    scan_method = models.CharField(max_length=10, choices=SCAN_METHOD_CHOICES, default=QR)
    booking_reference = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=120, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=SUCCESS)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["devotee", "timestamp"])]

    def __str__(self):
        return f"{self.devotee} · {self.check_type} · {self.timestamp:%Y-%m-%d %H:%M}"


class ScanHistory(models.Model):
    DEVOTEE, VOLUNTEER = "devotee", "volunteer"
    USER_TYPE_CHOICES = [(DEVOTEE, "Devotee"), (VOLUNTEER, "Volunteer")]
    QR, MANUAL = "QR", "MANUAL"
    SCAN_METHOD_CHOICES = [(QR, "QR"), (MANUAL, "Manual")]
    SUCCESS, FAILED = "SUCCESS", "FAILED"
    SCAN_STATUS_CHOICES = [(SUCCESS, "Success"), (FAILED, "Failed")]

    encrypted_qr = models.TextField(blank=True, help_text="Raw string received from the scanner — kept for audit/forensics.")
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, blank=True)
    devotee = models.ForeignKey("devotees.Devotee", on_delete=models.SET_NULL, null=True, blank=True, related_name="scan_history")
    volunteer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="scan_history")
    scan_method = models.CharField(max_length=10, choices=SCAN_METHOD_CHOICES, default=QR)
    action_type = models.CharField(max_length=20, blank=True)
    booking_reference = models.CharField(max_length=40, blank=True)
    scan_time = models.DateTimeField(auto_now_add=True, db_index=True)
    scan_status = models.CharField(max_length=10, choices=SCAN_STATUS_CHOICES)
    device_ip = models.GenericIPAddressField(null=True, blank=True)
    response_message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-scan_time"]

    def __str__(self):
        return f"{self.user_type or '?'} scan · {self.scan_status} · {self.scan_time:%Y-%m-%d %H:%M}"


class DevoteeQRStatus(models.Model):
    """The two PERMANENT QR payloads for a devotee — Temple Entry (used for
    both check-in and check-out) and Meal. Generated exactly once, the
    moment the Devotee row is created (see the post_save signal on
    Devotee), and never rebuilt after that. `/api/devotees/me/qr-data/`
    just reads these back — it does not mint anything new on GET.
    """

    devotee = models.OneToOneField("devotees.Devotee", on_delete=models.CASCADE, related_name="qr_status")
    entry_qr_token = models.TextField()
    meal_qr_token = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Devotee QR statuses"

    def __str__(self):
        return f"QR · {self.devotee}"

    @classmethod
    def get_or_create_for_devotee(cls, devotee) -> "DevoteeQRStatus":
        existing = cls.objects.filter(devotee=devotee).first()
        if existing:
            return existing

        # Local import avoids a circular import (qr_generator -> utils, and
        # models shouldn't need qr_generator at module load time).
        from .qr_generator import build_devotee_entry_qr, build_devotee_meal_qr

        entry_token, _ = build_devotee_entry_qr(devotee)
        meal_token, _ = build_devotee_meal_qr(devotee)
        return cls.objects.create(devotee=devotee, entry_qr_token=entry_token, meal_qr_token=meal_token)


class MealCollection(models.Model):
    """One row per successful meal scan. Entirely separate from Attendance —
    the Meal QR never touches temple entry/exit logic."""

    SUCCESS, FAILED = "SUCCESS", "FAILED"
    STATUS_CHOICES = [(SUCCESS, "Success"), (FAILED, "Failed")]

    devotee = models.ForeignKey("devotees.Devotee", on_delete=models.CASCADE, related_name="meal_collections")
    volunteer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="meal_collections_recorded")
    location = models.CharField(max_length=120, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=SUCCESS)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["devotee", "timestamp"])]

    def __str__(self):
        return f"{self.devotee} · meal · {self.timestamp:%Y-%m-%d %H:%M}"

    @classmethod
    def already_collected_today(cls, devotee) -> bool:
        """Guards against a permanent, never-expiring Meal QR being scanned
        twice in one day. Remove this check if repeated same-day meal
        collection should be allowed."""
        today = timezone.localdate()
        return cls.objects.filter(devotee=devotee, status=cls.SUCCESS, timestamp__date=today).exists()


class CrowdStatus(models.Model):
    """Latest crowd condition reported for a single temple area.

    One row per area — volunteers overwrite their own area's row rather than
    appending history, so "latest status by area" is always a plain query.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CROWD_LEVEL_CHOICES = [
        (LOW, "Low"),
        (MODERATE, "Moderate"),
        (HIGH, "High"),
    ]

    assigned_area = models.CharField(max_length=120, unique=True)
    crowd_level = models.CharField(max_length=10, choices=CROWD_LEVEL_CHOICES, default=LOW)
    approx_visitors = models.PositiveIntegerField(default=0)
    wait_time = models.PositiveIntegerField(default=0, help_text="Expected waiting time, in minutes")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crowd_status_updates",
    )
    timestamp = models.DateTimeField(auto_now=True)
    status = models.BooleanField(default=True, help_text="Active/inactive — inactive rows are hidden from the live dashboard")

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Crowd statuses"

    def __str__(self):
        return f"{self.assigned_area} — {self.get_crowd_level_display()}"


class VolunteerAreaAssignment(models.Model):
    """Which single area a volunteer is allowed to report crowd status for."""

    volunteer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="area_assignment",
    )
    assigned_area = models.CharField(max_length=120)

    def __str__(self):
        return f"{self.volunteer} → {self.assigned_area}"


class CrowdThresholds(models.Model):
    """Singleton config for the Low/Moderate/High recommendation engine.

    overall_crowd = Low   if current_inside <= low_max
                   = Moderate if current_inside <= moderate_max
                   = High  otherwise
    """

    low_max = models.PositiveIntegerField(default=500)
    moderate_max = models.PositiveIntegerField(default=1500)

    class Meta:
        verbose_name = "Crowd thresholds"
        verbose_name_plural = "Crowd thresholds"

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "CrowdThresholds":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Low ≤ {self.low_max} · Moderate ≤ {self.moderate_max} · High above that"





class ManualCounter(models.Model):
    """One row per +/- press on a volunteer's Manual Counter screen.
    `current manual count` for an area is never stored directly — it's
    always derived by summing this table, so the audit trail (used_by,
    reason, timestamp) and the running total can never drift apart."""

    INCREMENT, DECREMENT = "INCREMENT", "DECREMENT"
    ACTION_CHOICES = [(INCREMENT, "Increment"), (DECREMENT, "Decrement")]

    volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="manual_counter_entries",
    )
    assigned_area = models.CharField(max_length=120)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    count = models.PositiveIntegerField(default=1)
    reason = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [models.Index(fields=["assigned_area", "timestamp"])]

    def __str__(self):
        return f"{self.assigned_area} · {self.action} {self.count} · {self.timestamp:%Y-%m-%d %H:%M}"

    @classmethod
    def current_count_for_area(cls, area: str) -> int:
        agg = cls.objects.filter(assigned_area=area).aggregate(
            inc=Sum("count", filter=DBQ(action=cls.INCREMENT)),
            dec=Sum("count", filter=DBQ(action=cls.DECREMENT)),
        )
        return max((agg["inc"] or 0) - (agg["dec"] or 0), 0)

    @classmethod
    def today_stats_for_area(cls, area: str) -> dict:
        today = timezone.localdate()
        agg = cls.objects.filter(assigned_area=area, timestamp__date=today).aggregate(
            inc=Sum("count", filter=DBQ(action=cls.INCREMENT)),
            dec=Sum("count", filter=DBQ(action=cls.DECREMENT)),
        )
        return {"today_increment": agg["inc"] or 0, "today_decrement": agg["dec"] or 0}


# ---------------------------------------------------------------------
# Keep CrowdStatus.approx_visitors (and derived crowd_level) in sync
# every time a manual +/- is recorded, so admins see it live without a
# separate recompute step.
# ---------------------------------------------------------------------
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=ManualCounter, dispatch_uid="manual_counter_sync_crowd_status")
def _sync_crowd_status_on_manual_counter(sender, instance: "ManualCounter", created, **kwargs):
    if not created:
        return

    crowd_status, _ = CrowdStatus.objects.get_or_create(assigned_area=instance.assigned_area)

    delta = instance.count if instance.action == ManualCounter.INCREMENT else -instance.count
    crowd_status.approx_visitors = max(crowd_status.approx_visitors + delta, 0)

    thresholds = CrowdThresholds.load()
    if crowd_status.approx_visitors <= thresholds.low_max:
        crowd_status.crowd_level = CrowdStatus.LOW
    elif crowd_status.approx_visitors <= thresholds.moderate_max:
        crowd_status.crowd_level = CrowdStatus.MODERATE
    else:
        crowd_status.crowd_level = CrowdStatus.HIGH

    crowd_status.save(update_fields=["approx_visitors", "crowd_level", "timestamp"])