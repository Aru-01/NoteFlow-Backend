from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import OTPPurpose, OTPVerification, UserRole

User = get_user_model()


class AuthenticationAndOTPTests(APITestCase):
    def setUp(self):
        self.register_url = reverse("accounts:register")
        self.verify_otp_url = reverse("accounts:verify-otp")
        self.login_url = reverse("accounts:login")
        self.resend_otp_url = reverse("accounts:resend-otp")
        self.password_reset_request_url = reverse("accounts:password-reset-request")
        self.password_reset_confirm_url = reverse("accounts:password-reset-confirm")
        self.profile_url = reverse("accounts:profile")

        self.user_email = "testuser@example.com"
        self.user_password = "SecurePassword123!"

    def test_registration_creates_unverified_user_and_generates_otp(self):
        response = self.client.post(
            self.register_url,
            {
                "email": self.user_email,
                "password": self.user_password,
                "confirm_password": self.user_password,
                "interests": ["chess", "reading"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email=self.user_email)
        self.assertFalse(user.is_verified)
        self.assertEqual(user.role, UserRole.USER)
        self.assertEqual(user.interests, ["chess", "reading"])

        # Check OTP created in DB
        otp = OTPVerification.objects.filter(user=user, purpose=OTPPurpose.REGISTRATION).first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.otp_code), 6)

    def test_unverified_user_cannot_login(self):
        # Register first
        self.client.post(
            self.register_url,
            {
                "email": self.user_email,
                "password": self.user_password,
                "confirm_password": self.user_password,
            },
        )
        # Attempt login before verifying OTP
        login_response = self.client.post(
            self.login_url,
            {"email": self.user_email, "password": self.user_password},
        )
        self.assertEqual(login_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", login_response.data)

    def test_verify_otp_activates_user_and_deletes_otp_from_db(self):
        # Register
        self.client.post(
            self.register_url,
            {
                "email": self.user_email,
                "password": self.user_password,
                "confirm_password": self.user_password,
            },
        )
        user = User.objects.get(email=self.user_email)
        otp = OTPVerification.objects.get(user=user, purpose=OTPPurpose.REGISTRATION)

        # Wrong OTP fails
        fail_response = self.client.post(
            self.verify_otp_url,
            {"email": self.user_email, "otp_code": "000000", "purpose": "registration"},
        )
        self.assertEqual(fail_response.status_code, status.HTTP_400_BAD_REQUEST)

        # Correct OTP succeeds
        verify_response = self.client.post(
            self.verify_otp_url,
            {"email": self.user_email, "otp_code": otp.otp_code, "purpose": "registration"},
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.is_verified)

        # Verify OTP is completely removed from DB
        self.assertFalse(OTPVerification.objects.filter(id=otp.id).exists())

        # Login now succeeds
        login_response = self.client.post(
            self.login_url,
            {"email": self.user_email, "password": self.user_password},
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)
        self.assertEqual(login_response.data["user"]["email"], self.user_email)

    def test_password_reset_flow_with_otp(self):
        # Create verified user
        user = User.objects.create_user(
            email=self.user_email,
            password=self.user_password,
            is_verified=True,
        )

        # Request reset OTP
        reset_req_resp = self.client.post(
            self.password_reset_request_url,
            {"email": self.user_email},
        )
        self.assertEqual(reset_req_resp.status_code, status.HTTP_200_OK)

        otp = OTPVerification.objects.filter(user=user, purpose=OTPPurpose.PASSWORD_RESET).first()
        self.assertIsNotNone(otp)

        new_password = "BrandNewPassword456!"
        confirm_resp = self.client.post(
            self.password_reset_confirm_url,
            {
                "email": self.user_email,
                "otp_code": otp.otp_code,
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)

        # OTP is deleted
        self.assertFalse(OTPVerification.objects.filter(id=otp.id).exists())

        # Login with new password works
        login_resp = self.client.post(
            self.login_url,
            {"email": self.user_email, "password": new_password},
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)


class AdminUserManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
        )
        self.normal_user = User.objects.create_user(
            email="regular@example.com",
            password="UserPassword123!",
            is_verified=True,
        )
        self.admin_users_url = reverse("accounts:admin-user-list-create")

    def test_regular_user_cannot_access_admin_user_list(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get(self.admin_users_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_and_create_users(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.admin_users_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Contains results with pagination
        self.assertIn("results", response.data)

        # Admin creates new user with specific role
        create_resp = self.client.post(
            self.admin_users_url,
            {
                "email": "createdbyadmin@example.com",
                "password": "TempPassword123!",
                "role": "admin",
                "is_verified": True,
            },
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_resp.data["role"], "admin")
