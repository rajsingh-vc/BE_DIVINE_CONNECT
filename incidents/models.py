from django.conf import settings
from django.db import models


class IncidentReport(models.Model):
    """
    Incident Log shown on the Command Centre.

    - Created / edited / deleted by volunteers (their own reports only).
    - Viewable by everyone who is logged in (admin + devotee + volunteer).
    - Admin can additionally update status / severity on any report
      (e.g. to mark it resolved, escalate it, or reassign it).
    """

    class Category(models.TextChoices):
        MEDICAL = "medical", "Medical"
        CROWD = "crowd", "Crowd"
        SECURITY = "security", "Security"
        QUEUE = "queue", "Queue"
        VOLUNTEER_SUPPORT = "volunteer_support", "Volunteer Support"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    incident_code = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=Category.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.LOW)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    description = models.TextField()
    image = models.ImageField(upload_to="incidents/%Y/%m/", blank=True, null=True)
    location = models.CharField(max_length=150, blank=True, default="")

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incident_reports",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_incident_reports",
    )
    resolution_notes = models.TextField(blank=True, default="")
    responded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["incident_code"]),
            models.Index(fields=["category"]),
            models.Index(fields=["severity"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.incident_code:
            last = IncidentReport.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.incident_code = f"INC-{3000 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.incident_code} - {self.title}"

    @property
    def response_status(self):
        """'responded' once an admin has written something in resolution_notes,
        otherwise 'awaiting_response'. Independent of the open/in-progress/
        resolved/closed workflow status."""
        return "responded" if self.resolution_notes.strip() else "awaiting_response"