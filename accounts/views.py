from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import OTPPurpose, OTPVerification
from .permissions import IsAdminUserRole, IsVerifiedUser
from .serializers import (
    AdminUserSerializer,
    CustomTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ResendOTPSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    VerifyOTPSerializer,
)
from .utils import send_otp_email

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    Registers a new user in unverified state and sends a 6-digit verification OTP.
    """

    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="User Registration",
        description="Registers a new user and sends a 6-digit OTP to the registered email.",
        responses={
            201: OpenApiResponse(description="Registration successful, OTP dispatched.")
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "success": True,
                "message": "Account registered successfully. A 6-digit verification OTP has been sent to your email.",
                "data": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "is_verified": user.is_verified,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyOTPView(views.APIView):
    """
    Verifies 6-digit OTP code and removes it from the database immediately.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Verify OTP Code",
        description="Verifies the 6-digit code. For registration, activates user account.",
        request=VerifyOTPSerializer,
        responses={200: OpenApiResponse(description="OTP verified successfully.")},
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        purpose = serializer.validated_data["purpose"]

        action_msg = (
            "Account verified successfully. You can now log in."
            if purpose == OTPPurpose.REGISTRATION
            else "OTP verified successfully. You may proceed."
        )

        return Response(
            {
                "success": True,
                "message": action_msg,
                "data": {
                    "email": user.email,
                    "is_verified": user.is_verified,
                },
            },
            status=status.HTTP_200_OK,
        )


class ResendOTPView(views.APIView):
    """
    Regenerates a fresh 6-digit OTP and deletes any previous stale OTP.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Resend OTP Code",
        description="Generates a new 6-digit OTP with refreshed expiry and dispatches it via email.",
        request=ResendOTPSerializer,
        responses={200: OpenApiResponse(description="New OTP sent successfully.")},
    )
    def post(self, request, *args, **kwargs):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        purpose = serializer.validated_data["purpose"]

        otp_instance = OTPVerification.generate_otp(user=user, purpose=purpose)
        send_otp_email(user=user, otp_code=otp_instance.otp_code, purpose=purpose)

        return Response(
            {
                "success": True,
                "message": "A fresh 6-digit OTP code has been dispatched to your email address.",
            },
            status=status.HTTP_200_OK,
        )


class LoginView(TokenObtainPairView):
    """
    Authenticates user and returns JWT access & refresh tokens.
    Rejects users whose email OTP is not yet verified.
    """

    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="JWT Login",
        description="Obtains JWT token pair (Access & Refresh). Requires verified account.",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PasswordResetRequestView(views.APIView):
    """
    Initiates password recovery by sending a 6-digit OTP to the user's email.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Request Password Reset OTP",
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description="Password reset OTP sent.")},
    )
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.get(email=email)
        otp_instance = OTPVerification.generate_otp(
            user=user, purpose=OTPPurpose.PASSWORD_RESET
        )
        send_otp_email(
            user=user, otp_code=otp_instance.otp_code, purpose=OTPPurpose.PASSWORD_RESET
        )

        return Response(
            {
                "success": True,
                "message": "Password reset 6-digit OTP has been sent to your email address.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(views.APIView):
    """
    Validates OTP and updates the user's password. Consumes and deletes the OTP.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Confirm Password Reset",
        request=PasswordResetConfirmSerializer,
        responses={200: OpenApiResponse(description="Password reset successfully.")},
    )
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Your password has been successfully reset. You can now log in with your new password.",
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    View or update the authenticated user's profile (interests, username).
    """

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsVerifiedUser]

    @extend_schema(
        summary="Get/Update Current User Profile",
        description="Retrieve or modify profile data (interests, username) for the authenticated user.",
    )
    def get_object(self):
        return self.request.user


class AdminUserListCreateView(generics.ListCreateAPIView):
    """
    Admin endpoint to list all users (paginated & indexed) or create a new user with any role.
    """

    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    queryset = User.objects.all().order_by("-created_at")

    @extend_schema(
        summary="Admin: List & Create Users",
        description="Allows administrators to view all users with pagination or create a new user.",
    )
    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role=role)
        return queryset


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin endpoint to view, update, or remove any user.
    """

    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    queryset = User.objects.all()

    @extend_schema(
        summary="Admin: Manage Specific User",
        description="Allows administrators to retrieve, modify (role, status), or delete a specific user.",
    )
    def get_object(self):
        return super().get_object()
