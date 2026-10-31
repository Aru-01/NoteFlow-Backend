from django.urls import path
from .views import (
    AdminUserDetailView,
    AdminUserListCreateView,
    DecoratedTokenRefreshView,
    LoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    RegisterView,
    ResendOTPView,
    VerifyOTPView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", DecoratedTokenRefreshView.as_view(), name="token-refresh"),
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("profile/", ProfileView.as_view(), name="profile"),
    path(
        "admin/users/", AdminUserListCreateView.as_view(), name="admin-user-list-create"
    ),
    path(
        "admin/users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"
    ),
]
