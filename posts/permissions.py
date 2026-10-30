from rest_framework import permissions


class IsAuthorOrAdmin(permissions.BasePermission):
    """
    Object-level permission allowing only the author or an admin to edit/delete a post.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_verified
        )

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin" or request.user.is_superuser:
            return True
        return obj.author == request.user
