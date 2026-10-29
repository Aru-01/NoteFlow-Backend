from rest_framework import permissions


class IsOwnerOrAdminReadOnly(permissions.BasePermission):
    """
    Object-level permission allowing owners full control (read/write/delete),
    and administrators read access to all notes (or full control if permitted).
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_verified
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin" or request.user.is_superuser:
            return True
        return obj.owner == request.user
