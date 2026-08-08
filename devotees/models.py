from django.conf import settings
from django.db import models


class Devotee(models.Model):
    class Tier(models.TextChoices):
        MEMBER = "member", "Member"
        VIP = "vip", "VIP"

    # Nullable: a devotee profile can either be linked to a login (self-signup)
    # or be a walk-in record created directly by staff from the console — in
    # that case there's no user account, so name/email live on this model.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devotee_profile", null=True, blank=True
    )
    devotee_code = models.CharField(max_length=20, unique=True, editable=False)

    # Split name fields — power the "Online Seva Booking" form (First /
    # Middle / Last Name). `full_name` is kept and auto-derived from these
    # in save() so every existing query/serializer/search field that reads
    # `full_name` (Bookings, Bills, admin search, etc.) keeps working
    # unchanged.
    full_name = models.CharField(max_length=150, blank=True, default="")
    first_name = models.CharField(max_length=100, blank=True, default="")
    middle_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")

    email = models.EmailField(blank=True, default="")
    mobile = models.CharField(max_length=20, blank=True, default="")
    whatsapp = models.CharField(max_length=20, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")

    # NEW — "Online Seva Booking" form fields.
    address = models.TextField(blank=True, default="")
    pincode = models.CharField(max_length=10, blank=True, default="")
    pan_number = models.CharField(max_length=10, blank=True, default="")

    # NEW — set when a volunteer brings a devotee in / helps them register,
    # so the booking/billing flow can credit the referring volunteer.
    # Mirrors the existing Bill.volunteer attribution FK in bookings/models.py.
    referred_by_volunteer = models.ForeignKey(
        "volunteers.Volunteer", on_delete=models.SET_NULL, null=True, blank=True, related_name="referred_devotees"
    )

    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.MEMBER)

    # NEW — VIP quick-add flow only ("VIP Devotee Registration" page):
    # how many guests this VIP is bringing. Null/blank for every regular,
    # non-VIP devotee record — only ever set by DevoteeViewSet.register()
    # when is_vip=true, via DevoteeRegistrationSerializer.
    guest_count = models.PositiveIntegerField(null=True, blank=True, default=None)

    visits = models.PositiveIntegerField(default=0)
    total_donated = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["devotee_code"]),
            models.Index(fields=["city"]),
            models.Index(fields=["mobile"]),  # NEW — powers "enter mobile number to fetch address"
        ]

    def save(self, *args, **kwargs):
        if not self.devotee_code:
            last = Devotee.objects.order_by("-id").first()
            next_id = (last.id + 1) if last else 1
            self.devotee_code = f"DVT-{10000 + next_id}"
        # Keep full_name in sync whenever the split name fields are used. If a
        # caller sets full_name directly without touching first/last (existing
        # walk-in/staff creation flows), full_name is left exactly as given.
        if self.first_name or self.last_name:
            self.full_name = " ".join(p for p in [self.first_name, self.middle_name, self.last_name] if p)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.devotee_code} - {self.full_name}"