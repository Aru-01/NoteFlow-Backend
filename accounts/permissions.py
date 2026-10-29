from rest_framework import permissions


class IsAdminUserRole(permissions.BasePermission):
    """
    Allows access only to authenticated users who have the 'admin' role
    or superuser status.
    """
    message = "Only administrators have access to this resource."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == "admin" or request.user.is_superuser)
        )


class IsVerifiedUser(permissions.BasePermission):
    """
    Allows access only to users who have completed email OTP verification.
    """
    message = "Your email address is not verified. Please verify your OTP first."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_verified
        )


class IsSelfOrAdmin(permissions.BasePermission):
    """
    Allows a user to access/modify their own object, or allows full access to admins.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin" or request.user.is_superuser:
            return True
        return obj == request.user
