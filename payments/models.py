# payments/models.py
import uuid
from django.db import models


class SevaPayment(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seva_name = models.CharField(max_length=255)
    amount = models.PositiveIntegerField(help_text="Amount in paise (subunits)")
    currency = models.CharField(max_length=10, default="INR")
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    receipt = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seva_name} · {self.razorpay_order_id} · {self.payment_status}"