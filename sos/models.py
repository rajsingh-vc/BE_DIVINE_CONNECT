from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SOSAlert(models.Model):
    """
    Emergency SOS — the one-tap panic button on the Command Centre.

    A volunteer taps one of five preset emergency buttons (Fire, Lost
    Child/Item, Security, Medical, Volunteer Support). The alert fires
    immediately carrying the volunteer's identity, a server-side timestamp,
    and best-effort device location — free-text description and a photo are
    optional so the tap itself is never blocked waiting on typing.

    - Created by volunteers (and admins, e.g. for a manual/phoned-in entry).
      Devotees may also raise one, but only a Lost Child / Item alert.
    - Viewable by everyone logged in (admin + devotee + volunteer), same
      visibility model as the Incident Log.
    - Volunteers can edit/delete their own alerts (e.g. false alarm);
      admins can edit/delete any alert and are the only ones who can move
      the workflow status or write a response.
    """

    class AlertType(models.TextChoices):
        FIRE = "fire", "Fire"
        LOST_CHILD_ITEM = "lost_child_item", "Lost Child / Item"
        SECURITY = "security", "Security"
        MEDICAL = "medical", "Medical"
        VOLUNTEER_SUPPORT = "volunteer_support", "Volunteer Support"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    # Alert types a devotee is allowed to raise. Defined after AlertType
    # since it references AlertType.LOST_CHILD_ITEM.
    DEVOTEE_ALLOWED_TYPES = {AlertType.LOST_CHILD_ITEM}

    sos_code = models.CharField(max_length=20, unique=True, editable=False)
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="sos/%Y/%m/", blank=True, null=True)

    # Best-effort device location captured the moment the button is tapped
    # (browser Geolocation API). `location` can also be a hand-typed zone
    # name (e.g. "Gate 3") when GPS is unavailable/denied — both are optional.
    location = models.CharField(max_length=150, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sos_alerts",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_sos_alerts",
    )
    resolution_notes = models.TextField(blank=True, default="")
    responded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sos_code"]),
            models.Index(fields=["alert_type"]),
            models.Index(fields=["status"]),
        ]

    def clean(self):
        super().clean()
        raiser = self.raised_by
        if raiser and getattr(raiser, "user_type", None) == "devotee":
            if self.alert_type not in self.DEVOTEE_ALLOWED_TYPES:
                raise ValidationError(
                    {"alert_type": "Devotees can only raise a Lost Child / Item alert."}
                )

    def save(self, *args, **kwargs):
        if not self.sos_code:
            last = SOSAlert.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.sos_code = f"SOS-{5000 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sos_code} - {self.get_alert_type_display()}"

    @property
    def response_status(self):
        """'responded' once an admin has written something in resolution_notes,
        otherwise 'awaiting_response'. Independent of the open/in-progress/
        resolved/closed workflow status."""
        return "responded" if self.resolution_notes.strip() else "awaiting_response"