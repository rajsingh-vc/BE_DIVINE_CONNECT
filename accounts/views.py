from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from firebase_admin import auth as firebase_auth

from .firebase import verify_firebase_id_token
from .serializers import (
    DevoteeSignupSerializer,
    ForgotPasswordRequestSerializer,
    GoogleAuthSerializer,
    LoginSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VolunteerSignupSerializer,
)

User = get_user_model()


def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


class DevoteeSignupView(generics.CreateAPIView):
    serializer_class = DevoteeSignupSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, **tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class VolunteerSignupView(generics.CreateAPIView):
    serializer_class = VolunteerSignupSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, **tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class GoogleLoginView(APIView):
    """
    POST /api/auth/google/
    Body:
    {
      "firebase_id_token": "...",
      "name": "...",
      "email": "...",
      "photo_url": "..."
    }
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token = serializer.validated_data["firebase_id_token"]

        try:
            decoded = verify_firebase_id_token(id_token)
            print("Firebase decoded token:", decoded)
        except firebase_auth.ExpiredIdTokenError as e:
            return Response(
                {"detail": f"Expired Firebase token: {str(e)}"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except firebase_auth.InvalidIdTokenError as e:
            return Response(
                {"detail": f"Invalid Firebase token: {str(e)}"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except firebase_auth.RevokedIdTokenError as e:
            return Response(
                {"detail": f"Revoked Firebase token: {str(e)}"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except firebase_auth.CertificateFetchError as e:
            return Response(
                {"detail": f"Certificate fetch error: {str(e)}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as e:
            return Response(
                {"detail": f"Value error while verifying token: {str(e)}"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            return Response(
                {"detail": f"Firebase verify error: {type(e).__name__}: {str(e)}"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        firebase_uid = decoded.get("uid")
        email = decoded.get("email") or serializer.validated_data.get("email")
        full_name = decoded.get("name") or serializer.validated_data.get("name") or ""
        photo_url = decoded.get("picture") or serializer.validated_data.get("photo_url")

        if not firebase_uid:
            return Response(
                {"detail": "Firebase UID missing in verified token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email:
            return Response(
                {"detail": "Google account has no email on file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(firebase_uid=firebase_uid).first()

        if user is None:
            user = User.objects.filter(email__iexact=email).first()

            if user is None:
                user = User.objects.create(
                    username=email,
                    email=email,
                    full_name=full_name or email.split("@")[0],
                    user_type=User.UserType.DEVOTEE,
                    firebase_uid=firebase_uid,
                )
                user.set_unusable_password()
                user.save()

                try:
                    from devotees.models import Devotee

                    Devotee.objects.create(
                        user=user,
                        full_name=user.full_name,
                        email=user.email,
                    )
                except Exception as devotee_error:
                    print("Devotee profile create error:", devotee_error)
            else:
                update_fields = []

                if not user.firebase_uid:
                    user.firebase_uid = firebase_uid
                    update_fields.append("firebase_uid")

                if not user.full_name and full_name:
                    user.full_name = full_name
                    update_fields.append("full_name")

                if update_fields:
                    user.save(update_fields=update_fields)

        if not user.is_active:
            return Response(
                {"detail": "This account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "user": UserSerializer(user).data,
                "photo_url": photo_url,
                **tokens_for_user(user),
            },
            status=status.HTTP_200_OK,
        )


class BaseLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    allowed_user_type = None

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data["identifier"]
        password = serializer.validated_data["password"]

        try:
            user = User.objects.get(Q(email__iexact=identifier) | Q(phone=identifier))
        except User.DoesNotExist:
            return Response(
                {"detail": "User not find."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except User.MultipleObjectsReturned:
            user = User.objects.filter(
                Q(email__iexact=identifier) | Q(phone=identifier)
            ).first()

        if self.allowed_user_type and user.user_type != self.allowed_user_type:
            return Response(
                {"detail": "Invalid usertype."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {"detail": "Invalid password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "This account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {"user": UserSerializer(user).data, **tokens_for_user(user)},
            status=status.HTTP_200_OK,
        )


class DevoteeLoginView(BaseLoginView):
    allowed_user_type = User.UserType.DEVOTEE


class VolunteerLoginView(BaseLoginView):
    allowed_user_type = User.UserType.VOLUNTEER


class AdminLoginView(BaseLoginView):
    allowed_user_type = User.UserType.ADMIN


class LoginView(BaseLoginView):
    allowed_user_type = None


class ForgotPasswordRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        if not User.objects.filter(email__iexact=email).exists():
            return Response(
                {"detail": "Email not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"detail": "Email found", "email": email},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Email not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Password updated successfully"},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)