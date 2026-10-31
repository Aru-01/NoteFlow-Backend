from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

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
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Register New User",
        description="Registers a new user account with email and optional interests, then sends a 6-digit OTP code to the email for verification.",
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(description="Account registered successfully. Verification OTP sent via email."),
            400: OpenApiResponse(description="Validation error such as duplicate email or mismatched passwords."),
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
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Verify OTP Code",
        description="Validates a 6-digit OTP code against the registered email address. For registration, activates the account so the user can log in.",
        request=VerifyOTPSerializer,
        responses={
            200: OpenApiResponse(description="OTP verified successfully."),
            400: OpenApiResponse(description="Invalid or expired OTP code."),
        },
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
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Resend OTP Code",
        description="Generates a new 6-digit OTP code with fresh expiration and sends it to the user email.",
        request=ResendOTPSerializer,
        responses={
            200: OpenApiResponse(description="A fresh 6-digit OTP code has been dispatched to your email address."),
            400: OpenApiResponse(description="User does not exist or is already verified."),
        },
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
    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        tags=["auth"],
        summary="User Login (JWT)",
        description="Authenticates the user with email and password. Returns JWT access token, refresh token, and user profile data. Requires verified email.",
        responses={
            200: CustomTokenObtainPairSerializer,
            400: OpenApiResponse(description="Unverified account or invalid credentials."),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class DecoratedTokenRefreshView(TokenRefreshView):
    @extend_schema(
        tags=["auth"],
        summary="Refresh JWT Token",
        description="Takes a valid refresh token and returns a new JWT access token.",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PasswordResetRequestView(views.APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Request Password Reset OTP",
        description="Sends a 6-digit password reset OTP code to the given registered email address.",
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description="Password reset 6-digit OTP has been sent to your email address."),
            400: OpenApiResponse(description="No account found with this email address."),
        },
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
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Confirm Password Reset",
        description="Validates the 6-digit reset OTP and updates the user account with a new password.",
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description="Your password has been successfully reset. You can now log in."),
            400: OpenApiResponse(description="Invalid or expired OTP code, or passwords do not match."),
        },
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
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsVerifiedUser]

    @extend_schema(
        tags=["auth"],
        summary="Get Current User Profile",
        description="Retrieves the authenticated user profile information including role, interests, and verification status.",
        responses={200: UserProfileSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["auth"],
        summary="Update Current User Profile",
        description="Updates username or interests list for the authenticated user.",
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer},
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        tags=["auth"],
        summary="Partial Update Current User Profile",
        description="Partially updates username or interests list for the authenticated user.",
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_object(self):
        return self.request.user


class AdminUserListCreateView(generics.ListCreateAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    queryset = User.objects.all().order_by("-created_at")

    @extend_schema(
        tags=["auth"],
        summary="Admin: List Users",
        description="Allows administrators to retrieve a paginated list of all users, with optional filtering by role.",
        responses={200: AdminUserSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["auth"],
        summary="Admin: Create User",
        description="Allows administrators to create a new user account with designated role, verification status, and password.",
        request=AdminUserSerializer,
        responses={201: AdminUserSerializer},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role=role)
        return queryset


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    queryset = User.objects.all()

    @extend_schema(
        tags=["auth"],
        summary="Admin: Get User Details",
        description="Allows administrators to view details of any specific user by ID.",
        responses={200: AdminUserSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["auth"],
        summary="Admin: Full Update User",
        description="Allows administrators to update any user role, status, email, or profile fields.",
        request=AdminUserSerializer,
        responses={200: AdminUserSerializer},
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        tags=["auth"],
        summary="Admin: Partial Update User",
        description="Allows administrators to partially update user fields such as role or active status.",
        request=AdminUserSerializer,
        responses={200: AdminUserSerializer},
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        tags=["auth"],
        summary="Admin: Delete User",
        description="Allows administrators to permanently remove a specific user account.",
        responses={204: OpenApiResponse(description="User deleted successfully.")},
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def get_object(self):
        return super().get_object()
