import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_otp_email(user, otp_code: str, purpose: str):
    """
    Renders the modern minimalistic HTML OTP email and sends it via SMTP
    (or console backend in local development).
    """
    expiry_minutes = getattr(settings, "OTP_EXPIRY_MINUTES", 5)

    if purpose == "registration":
        subject = "Verify Your NoteFlow Account"
        title = "Email Verification"
        message = (
            "Thank you for joining NoteFlow! Please enter the 6-digit verification code below "
            "to activate your account and start managing your notes securely."
        )
    elif purpose == "password_reset":
        subject = "Reset Your NoteFlow Password"
        title = "Password Reset Request"
        message = (
            "We received a request to reset your NoteFlow password. "
            "Use the 6-digit code below to proceed with resetting your password."
        )
    else:
        subject = "Your NoteFlow Verification Code"
        title = "Verification Code"
        message = "Please use the 6-digit verification code below."

    context = {
        "username": user.username or user.email.split("@")[0],
        "title": title,
        "message": message,
        "otp_code": otp_code,
        "expiry_minutes": expiry_minutes,
    }

    try:
        html_content = render_to_string("emails/otp_email.html", context)
        plain_message = strip_tags(html_content)

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "NoteFlow <noreply@noteflow.local>")

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email to {user.email}: {e}")
        print(f"\n[NoteFlow DEV OTP] To: {user.email} | Purpose: {purpose} | Code: {otp_code} | Expiry: {expiry_minutes}m\n")
        return False
