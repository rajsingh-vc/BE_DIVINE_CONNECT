from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .models import OTP_MAX_VERIFY_ATTEMPTS, PasswordResetOTP
from .serializers import (
    ForgotPasswordResetSerializer,
    ForgotPasswordSendOTPSerializer,
    ForgotPasswordVerifyOTPSerializer,
)

User = get_user_model()


class _EmailScopedThrottle(SimpleRateThrottle):
    """Per-email rate limiting, on top of the per-cycle limits on the model itself."""

    def get_cache_key(self, request, view):
        email = (request.data.get("email") or "").strip().lower()
        ident = email or self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class SendOTPThrottle(_EmailScopedThrottle):
    scope = "forgot_password_send_otp"

    def get_rate(self):
        return "6/hour"


class VerifyOTPThrottle(_EmailScopedThrottle):
    scope = "forgot_password_verify_otp"

    def get_rate(self):
        return "20/hour"


def _send_otp_email(user, raw_otp):
    subject = "Your Divine Connect password reset code"
    message = (
        f"Hello {user.full_name or user.username},\n\n"
        f"Your one-time password to reset your Divine Connect password is:\n\n"
        f"    {raw_otp}\n\n"
        f"This code expires in 5 minutes. If you didn't request this, you can safely ignore this email.\n\n"
        f"— Divine Connect"
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )


class SendForgotPasswordOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SendOTPThrottle]

    def post(self, request):
        serializer = ForgotPasswordSendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"detail": "No account found with this email."}, status=status.HTTP_404_NOT_FOUND)

        otp_record, _created = PasswordResetOTP.objects.get_or_create(user=user)
        otp_record.start_new_cycle_if_stale()

        if otp_record.send_count > 0:
            cooldown_remaining = otp_record.seconds_until_resend_allowed()
            if cooldown_remaining > 0:
                return Response(
                    {"detail": f"Please wait {cooldown_remaining} seconds before requesting a new OTP."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        if otp_record.resends_remaining() <= 0:
            return Response(
                {"detail": "Maximum resend attempts reached. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        raw_otp = otp_record.issue_new_otp()
        otp_record.save()

        try:
            _send_otp_email(user, raw_otp)
        except Exception:
            return Response(
                {"detail": "Could not send the OTP email right now. Please try again shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"detail": "OTP has been sent to your registered email."}, status=status.HTTP_200_OK)


class VerifyForgotPasswordOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [VerifyOTPThrottle]

    def post(self, request):
        serializer = ForgotPasswordVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp_input = serializer.validated_data["otp"]

        user = User.objects.filter(email__iexact=email).first()
        otp_record = PasswordResetOTP.objects.filter(user=user).first() if user else None

        if not user or not otp_record or not otp_record.otp_hash:
            return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_record.is_expired():
            return Response({"detail": "OTP has expired. Please request a new OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_record.attempts >= OTP_MAX_VERIFY_ATTEMPTS:
            return Response(
                {"detail": "Maximum verification attempts exceeded. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp_record.check_otp(otp_input):
            otp_record.attempts += 1
            otp_record.save(update_fields=["attempts"])
            return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        reset_token = otp_record.issue_reset_token()
        otp_record.save()

        # reset_token is a short-lived, single-purpose secret — not the OTP itself.
        return Response({"detail": "OTP verified.", "reset_token": reset_token}, status=status.HTTP_200_OK)


class ResetForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        reset_token = serializer.validated_data["reset_token"]
        new_password = serializer.validated_data["new_password"]

        user = User.objects.filter(email__iexact=email).first()
        otp_record = PasswordResetOTP.objects.filter(user=user).first() if user else None

        if not user or not otp_record or not otp_record.is_verified or not otp_record.check_reset_token(reset_token):
            return Response(
                {"detail": "This reset session has expired. Please restart the forgot-password process."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        otp_record.invalidate()
        otp_record.save()

        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)