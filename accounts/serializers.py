import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of the logged-in user, returned after auth."""

    # NEW — the logged-in user's own Volunteer row id (not the User id), so
    # the frontend can pre-select "Referred by Volunteer" on the walk-in
    # entry form without an extra lookup. None for admins/devotees, or for
    # a volunteer account that somehow has no linked Volunteer row.
    volunteer_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "full_name", "user_type", "phone", "date_joined", "is_staff", "volunteer_id"]
        read_only_fields = fields

    def get_volunteer_id(self, obj):
        volunteer = getattr(obj, "volunteer_profile_v2", None)
        return volunteer.id if volunteer else None


class BaseSignupSerializer(serializers.ModelSerializer):
    """
    Shared signup serializer for Devotee / Volunteer signup.
    Validates email/phone uniqueness and password confirmation,
    then stores the password encrypted (Django's set_password -> PBKDF2 hash).

    There's no username field on the signup form — a unique username is
    generated internally so the underlying Django user model (which still
    requires one) stays satisfied.
    """

    confirm_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)

    user_type = None  # overridden by subclasses

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "phone", "password", "confirm_password"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exclude(phone="").exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs

    @staticmethod
    def _generate_username(email):
        base = email.split("@")[0][:20] or "user"
        username = base
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}-{uuid.uuid4().hex[:6]}"
        return username

    def create(self, validated_data):
        password = validated_data.pop("password")
        username = self._generate_username(validated_data["email"])
        user = User(user_type=self.user_type, username=username, **validated_data)
        user.set_password(password)  # stored encrypted, never in plaintext
        user.save()
        return user


class DevoteeSignupSerializer(BaseSignupSerializer):
    user_type = User.UserType.DEVOTEE

    def create(self, validated_data):
        user = super().create(validated_data)
        from devotees.models import Devotee

        Devotee.objects.create(user=user, full_name=user.full_name, email=user.email, mobile=user.phone)
        return user


class VolunteerSignupSerializer(BaseSignupSerializer):
    """
    Signup Restriction: a volunteer application does NOT create a login
    account by itself. A person may only sign up here once their Volunteer
    application has been submitted (via /volunteers/volunteers/apply/ or
    /register/) and subsequently Admin Approved. We look up that approved,
    not-yet-claimed application by email/phone and attach the new user to it
    instead of creating a brand new, disconnected Volunteer row.
    """

    user_type = User.UserType.VOLUNTEER

    def validate(self, attrs):
        attrs = super().validate(attrs)
        from volunteers.models import Volunteer

        email = attrs.get("email")
        phone = attrs.get("phone")

        application = (
            Volunteer.objects.filter(Q(email__iexact=email) | Q(phone=phone))
            .order_by("-created_at")
            .first()
        )

        if not application:
            raise serializers.ValidationError(
                {
                    "detail": "No volunteer application found for this email/phone. "
                    "Please apply as a volunteer first and wait for admin approval."
                }
            )

        if application.user_id:
            raise serializers.ValidationError(
                {"detail": "A volunteer account already exists for this application. Please sign in instead."}
            )

        rejected_statuses = (
            Volunteer.Status.VOLUNTEER_REJECTED,
            Volunteer.Status.ADMIN_REJECTED,
            Volunteer.Status.AUTO_REJECTED,
        )
        if application.status in rejected_statuses:
            raise serializers.ValidationError(
                {"detail": "Your volunteer application has been rejected. You are not eligible to create a volunteer account."}
            )

        if application.status != Volunteer.Status.ADMIN_APPROVED or not application.is_volunteer:
            raise serializers.ValidationError(
                {
                    "detail": "Your volunteer application is still pending approval. "
                    "You can sign up once an admin approves it."
                }
            )

        self._application = application
        return attrs

    def create(self, validated_data):
        user = super().create(validated_data)

        application = self._application
        application.user = user
        # Keep the approved application in sync with the login account details.
        application.name = user.full_name
        application.email = user.email
        application.phone = user.phone
        application.save(update_fields=["user", "name", "email", "phone"])
        return user


class GoogleAuthSerializer(serializers.Serializer):
    """Payload sent by the Flutter app after Firebase Google sign-in."""

    firebase_id_token = serializers.CharField()
    name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    photo_url = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class LoginSerializer(serializers.Serializer):
    """Accepts either an email address or a phone number in the `identifier` field, plus password."""

    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)


class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


# ---------------------------------------------------------------------------
# OTP-based forgot-password flow (replaces the plain email-only flow above).
# Kept ForgotPasswordRequestSerializer / ResetPasswordSerializer untouched
# above in case anything else still points at them — safe to delete once
# your views/urls are fully switched over to the OTP endpoints below.
# ---------------------------------------------------------------------------


class ForgotPasswordSendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ForgotPasswordVerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.RegexField(regex=r"^\d{6}$", error_messages={"invalid": "Invalid OTP."})


class ForgotPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    reset_token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs