from datetime import datetime

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Seva(models.Model):
    """A seva/service offered by the sansthan (used by Bookings + Sevas & Services page)."""

    name = models.CharField(max_length=150, unique=True)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(default=30)
    slots_per_day = models.PositiveIntegerField(default=1)
    capacity = models.PositiveIntegerField(default=1)
    priest = models.CharField(max_length=150, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)

    # --- Daily Seva scheduling, used to auto-drive Live Festival Info ---
    start_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["category"]), models.Index(fields=["is_popular"])]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------
    # Schedule helpers — used by SevaSerializer (is_live/is_bookable) and
    # BookingSerializer.validate() (has_valid_schedule/start_datetime/
    # end_datetime). Keeping these as properties means there's a single
    # source of truth instead of duplicated datetime-combining logic.
    # ------------------------------------------------------------------
    @property
    def has_valid_schedule(self):
        return all([self.start_date, self.start_time, self.end_date, self.end_time])

    @property
    def start_datetime(self):
        if not self.has_valid_schedule:
            return None
        naive = datetime.combine(self.start_date, self.start_time)
        return timezone.make_aware(naive) if timezone.is_naive(naive) else naive

    @property
    def end_datetime(self):
        if not self.has_valid_schedule:
            return None
        naive = datetime.combine(self.end_date, self.end_time)
        return timezone.make_aware(naive) if timezone.is_naive(naive) else naive

    @property
    def is_live(self):
        """True if right now falls within this Seva's booking window."""
        if not self.has_valid_schedule:
            return False
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime

    @property
    def is_bookable(self):
        """Active AND currently live — what the frontend should gate on."""
        return self.is_active and self.is_live


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Channel(models.TextChoices):
        WEB = "web", "Web"
        MOBILE = "mobile", "Mobile"
        COUNTER = "counter", "Counter"
        WHATSAPP = "whatsapp", "WhatsApp"

    booking_code = models.CharField(max_length=20, unique=True, editable=False)
    devotee = models.ForeignKey("devotees.Devotee", on_delete=models.CASCADE, related_name="bookings")
    seva = models.ForeignKey(Seva, on_delete=models.PROTECT, related_name="bookings")
    date = models.DateField()
    slot = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WEB)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    payment_id = models.CharField(max_length=100, blank=True, default="")
    bill = models.OneToOneField(
        "bookings.Bill", on_delete=models.SET_NULL, null=True, blank=True, related_name="booking"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bookings_created",
    )

    encrypted_qr = models.TextField(blank=True, default="")
    qr_generated_at = models.DateTimeField(null=True, blank=True)
    qr_scanned_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    used_by_volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="seva_bookings_scanned",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["booking_code"]), models.Index(fields=["date"]), models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        if not self.booking_code:
            last = Booking.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.booking_code = f"BKG-{50000 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.booking_code


class Bill(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    bill_number = models.CharField(max_length=20, unique=True, editable=False)
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)

    devotee = models.ForeignKey("devotees.Devotee", on_delete=models.PROTECT, related_name="bills")
    seva = models.ForeignKey(Seva, on_delete=models.PROTECT, related_name="bills")
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="bills_created"
    )
    volunteer = models.ForeignKey(
        "volunteers.Volunteer", on_delete=models.SET_NULL, null=True, blank=True, related_name="referred_bills"
    )

    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    razorpay_order_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_signature = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["bill_number"]),
            models.Index(fields=["payment_status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.bill_number:
            last = Bill.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.bill_number = f"BILL{next_id:05d}"
            self.invoice_number = f"INV-{1000 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.bill_number


class MealBooking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    booking_code = models.CharField(max_length=20, unique=True, editable=False)
    devotee = models.ForeignKey("devotees.Devotee", on_delete=models.CASCADE, related_name="meal_bookings")
    meal_name = models.CharField(max_length=150)
    meal_date = models.DateField()
    meal_time = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    encrypted_qr = models.TextField(blank=True, default="")
    qr_generated_at = models.DateTimeField(null=True, blank=True)
    qr_scanned_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    used_by_volunteer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="meal_bookings_scanned",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["booking_code"]), models.Index(fields=["meal_date"]), models.Index(fields=["status"])]

    def save(self, *args, **kwargs):
        if not self.booking_code:
            last = MealBooking.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.booking_code = f"ML-{5000 + next_id}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.booking_code


@receiver(post_save, sender=Booking, dispatch_uid="generate_seva_booking_qr")
def _generate_seva_booking_qr(sender, instance: "Booking", created, **kwargs):
    if instance.status != Booking.Status.CONFIRMED or instance.encrypted_qr:
        return
    from .booking_qr import build_seva_booking_qr
    token = build_seva_booking_qr(instance)
    Booking.objects.filter(pk=instance.pk).update(encrypted_qr=token, qr_generated_at=timezone.now())


@receiver(post_save, sender=MealBooking, dispatch_uid="generate_meal_booking_qr")
def _generate_meal_booking_qr(sender, instance: "MealBooking", created, **kwargs):
    if instance.status != MealBooking.Status.CONFIRMED or instance.encrypted_qr:
        return
    from .booking_qr import build_meal_booking_qr
    token = build_meal_booking_qr(instance)
    MealBooking.objects.filter(pk=instance.pk).update(encrypted_qr=token, qr_generated_at=timezone.now())