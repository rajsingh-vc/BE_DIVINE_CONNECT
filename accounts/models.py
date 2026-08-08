from django.contrib.auth.models import AbstractUser
from django.db import models


import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

OTP_VALIDITY_MINUTES = 5
OTP_MAX_VERIFY_ATTEMPTS = 5
OTP_MAX_SENDS_PER_CYCLE = 4  # 1 initial send + 3 resends
OTP_RESEND_COOLDOWN_SECONDS = 30
OTP_CYCLE_WINDOW = timedelta(hours=1)
RESET_TOKEN_VALIDITY_MINUTES = 10


class PasswordResetOTP(models.Model):
    """
    One row per user for the forgot-password flow. The row is reused across
    send/resend/verify — never store the raw OTP, only its hash. A `cycle`
    is the 1-hour window that bounds how many sends/attempts are allowed;
    it auto-resets after OTP_CYCLE_WINDOW so a user isn't locked out forever.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_otp"
    )
    otp_hash = models.CharField(max_length=128, blank=True, default="")
    cycle_started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=timezone.now)
    last_sent_at = models.DateTimeField(default=timezone.now)
    send_count = models.PositiveSmallIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    reset_token_hash = models.CharField(max_length=128, blank=True, default="")
    reset_token_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_password_reset_otp"

    def __str__(self):
        return f"PasswordResetOTP(user_id={self.user_id})"

    # ---- cycle bookkeeping -------------------------------------------------

    def start_new_cycle_if_stale(self):
        """Reset counters once the previous send cycle is more than an hour old."""
        if timezone.now() - self.cycle_started_at > OTP_CYCLE_WINDOW:
            self.cycle_started_at = timezone.now()
            self.send_count = 0
            self.attempts = 0
            self.is_verified = False
            self.reset_token_hash = ""
            self.reset_token_expires_at = None

    def seconds_until_resend_allowed(self):
        elapsed = (timezone.now() - self.last_sent_at).total_seconds()
        return max(0, int(OTP_RESEND_COOLDOWN_SECONDS - elapsed))

    def resends_remaining(self):
        return max(0, OTP_MAX_SENDS_PER_CYCLE - self.send_count)

    # ---- OTP lifecycle -------------------------------------------------

    def issue_new_otp(self):
        """Generate + hash a fresh OTP. Returns the RAW otp — email it, never persist it."""
        raw_otp = f"{secrets.randbelow(1_000_000):06d}"
        self.otp_hash = make_password(raw_otp)
        self.expires_at = timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)
        self.last_sent_at = timezone.now()
        self.send_count += 1
        self.attempts = 0
        self.is_verified = False
        self.reset_token_hash = ""
        self.reset_token_expires_at = None
        return raw_otp

    def is_expired(self):
        return timezone.now() > self.expires_at

    def check_otp(self, raw_otp):
        return bool(self.otp_hash) and check_password(raw_otp, self.otp_hash)

    # ---- reset token (bridges verify-otp -> reset-password) -----------

    def issue_reset_token(self):
        raw_token = secrets.token_urlsafe(32)
        self.reset_token_hash = make_password(raw_token)
        self.reset_token_expires_at = timezone.now() + timedelta(minutes=RESET_TOKEN_VALIDITY_MINUTES)
        self.is_verified = True
        return raw_token

    def check_reset_token(self, raw_token):
        if not self.reset_token_hash or not self.reset_token_expires_at:
            return False
        if timezone.now() > self.reset_token_expires_at:
            return False
        return check_password(raw_token, self.reset_token_hash)

    def invalidate(self):
        self.otp_hash = ""
        self.reset_token_hash = ""
        self.reset_token_expires_at = None
        self.is_verified = False

class User(AbstractUser):
    """
    Custom user model used for both Devotees and Volunteers (and staff/admin).
    `user_type` distinguishes the account type across the whole system.
    """

    class UserType(models.TextChoices):
        DEVOTEE = "devotee", "Devotee"
        VOLUNTEER = "volunteer", "Volunteer"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.DEVOTEE)
    phone = models.CharField(max_length=20, blank=True, default="")
    firebase_uid = models.CharField(max_length=255, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["user_type"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.username})"
