from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import OTPPurpose, OTPVerification, UserRole
from .utils import send_otp_email

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Handles user self-registration with email as the primary credential.
    Registers an unverified user and sends a 6-digit verification OTP.
    """

    email = serializers.EmailField(required=True)
    username = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        help_text="Optional display name. Defaults to email prefix if not provided.",
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )
    interests = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
        help_text="List of interests e.g. ['reading', 'chess']",
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "password",
            "confirm_password",
            "interests",
        )

    def validate_email(self, value):
        normalized_email = value.lower().strip()
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError(
                "A user with this email address already exists."
            )
        return normalized_email

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        interests = validated_data.get("interests", [])
        username = validated_data.get("username")

        user = User.objects.create_user(
            email=validated_data["email"],
            username=username,
            password=password,
            role=UserRole.USER,
            interests=interests,
            is_verified=False,
        )

        otp_instance = OTPVerification.generate_otp(
            user=user, purpose=OTPPurpose.REGISTRATION
        )
        send_otp_email(
            user=user, otp_code=otp_instance.otp_code, purpose=OTPPurpose.REGISTRATION
        )

        return user


class VerifyOTPSerializer(serializers.Serializer):
    """
    Validates a 6-digit OTP code against the user's email.
    If valid, deletes the OTP from the database and marks user as verified.
    """

    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=OTPPurpose.choices, default=OTPPurpose.REGISTRATION
    )

    def validate(self, attrs):
        email = attrs.get("email").lower().strip()
        otp_code = attrs.get("otp_code").strip()
        purpose = attrs.get("purpose")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "No account found with this email address."}
            )

        is_valid = OTPVerification.verify_and_consume(
            user=user, otp_code=otp_code, purpose=purpose
        )
        if not is_valid:
            raise serializers.ValidationError(
                {"otp_code": "Invalid or expired OTP code."}
            )

        if purpose == OTPPurpose.REGISTRATION:
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        attrs["user"] = user
        return attrs


class ResendOTPSerializer(serializers.Serializer):
    """
    Resends a new 6-digit OTP to the user's email and clears older ones.
    """

    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=OTPPurpose.choices, default=OTPPurpose.REGISTRATION
    )

    def validate(self, attrs):
        email = attrs.get("email").lower().strip()
        purpose = attrs.get("purpose")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "No account found with this email address."}
            )

        if purpose == OTPPurpose.REGISTRATION and user.is_verified:
            raise serializers.ValidationError(
                {"email": "This account is already verified."}
            )

        attrs["user"] = user
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT Token Serializer that authenticates via email & password,
    enforces email OTP verification, and embeds user data into the response.
    """

    def validate(self, attrs):
        # Authenticate email
        data = super().validate(attrs)

        if not self.user.is_verified:
            raise serializers.ValidationError(
                {
                    "detail": "Your email is not verified yet. Please verify your OTP to log in."
                }
            )

        data["user"] = {
            "id": self.user.id,
            "email": self.user.email,
            "username": self.user.username,
            "role": self.user.role,
            "interests": self.user.interests,
            "is_verified": self.user.is_verified,
        }
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Initiates password recovery by sending a 6-digit OTP to the email.
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        normalized = value.lower().strip()
        try:
            user = User.objects.get(email__iexact=normalized)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "No account found with this email address."
            )
        return normalized


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Verifies 6-digit OTP and resets the user's password. Removes OTP from DB.
    """

    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        email = attrs.get("email").lower().strip()
        otp_code = attrs.get("otp_code").strip()

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "No account found with this email address."}
            )

        # Verify user and OTP deletes
        is_valid = OTPVerification.verify_and_consume(
            user=user,
            otp_code=otp_code,
            purpose=OTPPurpose.PASSWORD_RESET,
        )
        if not is_valid:
            raise serializers.ValidationError(
                {"otp_code": "Invalid or expired OTP code."}
            )

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        new_password = self.validated_data["new_password"]
        user.set_password(new_password)
        user.is_verified = True
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing and updating user profile (interests, username).
    Role, email, and is_verified are read-only.
    """

    interests = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "role",
            "interests",
            "is_verified",
            "created_at",
        )
        read_only_fields = ("id", "email", "role", "is_verified", "created_at")


class AdminUserSerializer(serializers.ModelSerializer):
    """
    Serializer for Admin to manage users (add, remove, update, and list all users).
    Supports assigning roles ('user' or 'admin').
    """

    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    interests = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "password",
            "role",
            "interests",
            "is_verified",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        interests = validated_data.get("interests", [])
        role = validated_data.get("role", UserRole.USER)
        is_verified = validated_data.get("is_verified", True)
        username = validated_data.get("username")

        user = User.objects.create_user(
            email=validated_data["email"],
            username=username,
            password=password,
            role=role,
            interests=interests,
            is_verified=is_verified,
            is_active=validated_data.get("is_active", True),
        )
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
