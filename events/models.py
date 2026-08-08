from django.db import models


class Event(models.Model):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        CONFIRMED = "confirmed", "Confirmed"
        UPCOMING = "upcoming", "Upcoming"
        COMPLETED = "completed", "Completed"

    event_code = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=150)
    date = models.DateField()
    expected_visitors = models.CharField(max_length=50, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNING)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["date"]
        indexes = [models.Index(fields=["event_code"]), models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        if not self.event_code:
            last = Event.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.event_code = f"EVT-{70 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Visitor(models.Model):
    class Status(models.TextChoices):
        INSIDE = "inside", "Inside"
        EXITED = "exited", "Exited"

    visitor_code = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=150)
    check_in = models.DateTimeField(auto_now_add=True)
    check_out = models.DateTimeField(null=True, blank=True)
    zone = models.CharField(max_length=100, blank=True, default="")
    party_size = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INSIDE)

    class Meta:
        ordering = ["-check_in"]
        indexes = [models.Index(fields=["visitor_code"]), models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        if not self.visitor_code:
            last = Visitor.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.visitor_code = f"VIS-{9000 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.visitor_code
