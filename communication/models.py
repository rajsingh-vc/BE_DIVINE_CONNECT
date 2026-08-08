from django.db import models


class Announcement(models.Model):
    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        PUSH = "push", "Push Notification"

    title = models.CharField(max_length=200)
    message = models.TextField()
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    audience = models.CharField(max_length=100, default="all")
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
