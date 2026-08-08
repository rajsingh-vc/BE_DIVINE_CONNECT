from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .otp_views import ResetForgotPasswordView, SendForgotPasswordOTPView, VerifyForgotPasswordOTPView

from .views import (
    AdminLoginView,
    DevoteeLoginView,
    DevoteeSignupView,
    ForgotPasswordRequestView,
    GoogleLoginView,
    LoginView,
    MeView,
    ResetPasswordView,
    VolunteerLoginView,
    VolunteerSignupView,
)

urlpatterns = [
    path("devotee/signup/", DevoteeSignupView.as_view(), name="devotee-signup"),
    path("devotee/login/", DevoteeLoginView.as_view(), name="devotee-login"),
    path("google/", GoogleLoginView.as_view(), name="google-login"),
    path("volunteer/signup/", VolunteerSignupView.as_view(), name="volunteer-signup"),
    path("volunteer/login/", VolunteerLoginView.as_view(), name="volunteer-login"),
    path("admin/login/", AdminLoginView.as_view(), name="admin-login"),
    path("login/", LoginView.as_view(), name="login"),
    path("forgot-password/", ForgotPasswordRequestView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("forgot-password/send-otp/", SendForgotPasswordOTPView.as_view(), name="forgot-password-send-otp"),
    path("forgot-password/verify-otp/", VerifyForgotPasswordOTPView.as_view(), name="forgot-password-verify-otp"),
    path("forgot-password/reset-password/", ResetForgotPasswordView.as_view(), name="forgot-password-reset"),
]
