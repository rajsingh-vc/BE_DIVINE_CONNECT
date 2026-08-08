from django.db import models


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"
        BLOCKED = "blocked", "Blocked"

    task_code = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    assignee = models.CharField(max_length=150, blank=True, default="")
    due_date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["task_code"]), models.Index(fields=["status"]), models.Index(fields=["priority"])]

    def save(self, *args, **kwargs):
        if not self.task_code:
            last = Task.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.task_code = f"TSK-{1000 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.task_code} - {self.title}"