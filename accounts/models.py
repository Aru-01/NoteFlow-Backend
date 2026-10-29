import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    USER = "user", "User"
    ADMIN = "admin", "Admin"


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the primary unique identifier
    for authentication, with explicit role and verification handling.
    """

    def create_user(
        self, email, password=None, role=UserRole.USER, username=None, **extra_fields
    ):
        if not email:
            raise ValueError(_("The Email field must be set."))

        email = self.normalize_email(email)

        if not username:
            base_username = email.split("@")[0]
            username = base_username
            counter = 1
            while self.model.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", False)

        user = self.model(email=email, username=username, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, username=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(
            email=email,
            password=password,
            username=username,
            role=UserRole.ADMIN,
            **extra_fields,
        )


class User(AbstractUser):
    """
    Custom User model where email is the primary identifier.
    Supports role-based access control (User/Admin), email OTP verification,
    and user interests for aggregation.
    """

    email = models.EmailField(_("email address"), unique=True, db_index=True)
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="Optional display username. Defaults to email prefix if omitted.",
    )
    role = models.CharField(
        max_length=10,
        choices=UserRole.choices,
        default=UserRole.USER,
        db_index=True,
        help_text="Role determining user permissions (user/admin)",
    )
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether this user has verified their email via OTP.",
    )
    interests = models.JSONField(
        default=list,
        blank=True,
        help_text="List of user interests (e.g. ['chess', 'reading']) for profiling and aggregation.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["role", "created_at"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_admin_role(self):
        return self.role == UserRole.ADMIN or self.is_superuser


class OTPPurpose(models.TextChoices):
    REGISTRATION = "registration", "Registration"
    PASSWORD_RESET = "password_reset", "Password Reset"


class OTPVerification(models.Model):
    """
    Stores 6-digit OTP codes with expiry and purpose.
    Expired and consumed OTPs are deleted to maintain database hygiene.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otps"
    )
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=OTPPurpose.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "OTP Verification"
        verbose_name_plural = "OTP Verifications"
        indexes = [
            models.Index(fields=["user", "purpose"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"OTP({self.user.email} - {self.purpose} - {self.otp_code})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def clean_expired_otps(cls):
        """Purge all expired OTP records from the database."""
        cls.objects.filter(expires_at__lt=timezone.now()).delete()

    @classmethod
    def generate_otp(cls, user, purpose):
        """
        Generates a secure 6-digit numeric OTP with an expiry time.
        Removes any previous OTPs for this user and purpose.
        """
        cls.clean_expired_otps()
        cls.objects.filter(user=user, purpose=purpose).delete()

        otp_code = f"{secrets.randbelow(900000) + 100000}"
        expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 5)
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

        otp_instance = cls.objects.create(
            user=user,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=expires_at,
        )
        return otp_instance

    @classmethod
    def verify_and_consume(cls, user, otp_code, purpose):
        """
        Validates the OTP code for the user and purpose.
        If valid, removes the OTP immediately from the database and returns True.
        Otherwise returns False.
        """
        cls.clean_expired_otps()

        otp_instance = cls.objects.filter(
            user=user,
            otp_code=otp_code,
            purpose=purpose,
            expires_at__gte=timezone.now(),
        ).first()

        if otp_instance:
            otp_instance.delete()
            return True

        return False
