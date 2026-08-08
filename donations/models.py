from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models


class Donation(models.Model):
    class Purpose(models.TextChoices):
        GENERAL = "general", "General Fund"
        ANNADAAN = "annadaan", "Annadaan"
        CONSTRUCTION = "construction", "Construction"
        EDUCATION = "education", "Education"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    # Platform fee charged on top of every donation (percentage of amount).
    # Override with DONATION_PLATFORM_FEE_PERCENT in settings/.env if needed.
    PLATFORM_FEE_PERCENT = Decimal(str(getattr(settings, "DONATION_PLATFORM_FEE_PERCENT", "2.0")))

    donation_code = models.CharField(max_length=20, unique=True, editable=False)
    devotee = models.ForeignKey(
        "devotees.Devotee", on_delete=models.SET_NULL, null=True, blank=True, related_name="donations"
    )

    # --- Amount -------------------------------------------------------
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_anonymous = models.BooleanField(default=False)

    # --- Donor information ---------------------------------------------
    # Always captured for internal records/receipts, but never surfaced in
    # the bill summary (or anywhere donor-facing) when is_anonymous=True.
    donor_name = models.CharField(max_length=150, blank=True, default="")
    donor_email = models.EmailField(blank=True, default="")
    donor_mobile = models.CharField(max_length=20, blank=True, default="")
    donor_address = models.CharField(max_length=255, blank=True, default="")

    # --- Tax & receipt (optional 80G tax receipt) -----------------------
    want_80g_receipt = models.BooleanField(default=False)
    donor_pan = models.CharField(max_length=10, blank=True, default="")
    receipt_number = models.CharField(max_length=20, blank=True, default="")

    purpose = models.CharField(max_length=30, choices=Purpose.choices, default=Purpose.GENERAL)

    # --- Bill summary figures (auto-computed on save) -------------------
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # --- Payment ---------------------------------------------------------
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_reference = models.CharField(max_length=100, blank=True, default="")
    razorpay_order_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_signature = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["donation_code"]),
            models.Index(fields=["purpose"]),
            models.Index(fields=["payment_status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.donation_code:
            last = Donation.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.donation_code = f"DON-{70000 + next_id}"

        # Bill summary figures are always derived from `amount`, never
        # trusted from client input.
        self.platform_fee = self.calculate_platform_fee(self.amount)
        self.total_amount = (self.amount or Decimal("0")) + self.platform_fee

        if self.want_80g_receipt and not self.receipt_number:
            self.receipt_number = f"RCPT-{self.donation_code.split('-')[-1]}"

        # Anonymous donations never store a donor name against the record
        # that could leak into public-facing views.
        if self.is_anonymous:
            self.donor_name = ""

        super().save(*args, **kwargs)

    @classmethod
    def calculate_platform_fee(cls, amount):
        amount = Decimal(amount or 0)
        fee = amount * cls.PLATFORM_FEE_PERCENT / Decimal("100")
        return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def bill_summary(self):
        """Bill summary shown to the donor and in receipts. Donor name is
        withheld whenever the donation was made anonymously."""
        return {
            "donor": "Anonymous Donor" if self.is_anonymous else (self.donor_name or "Anonymous Donor"),
            "donation_amount": float(self.amount),
            "platform_fee": float(self.platform_fee),
            "total_amount": float(self.total_amount),
        }

    def __str__(self):
        return self.donation_code