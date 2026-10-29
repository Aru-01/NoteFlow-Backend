from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions
from .models import Note
from .permissions import IsOwnerOrAdminReadOnly
from .serializers import NoteSerializer
from accounts.permissions import IsVerifiedUser


class NoteListCreateView(generics.ListCreateAPIView):
    """
    List & Create Notes.
    - Regular users see only their own notes.
    - Administrators can view all users' notes (with optional user filtering).
    - Supports pagination, status/priority filtering, and keyword search.
    """

    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsVerifiedUser]

    @extend_schema(
        summary="List Notes or Create Note",
        description=(
            "List notes with pagination. Regular users only see their own notes. "
            "Admins see all notes. Supports filtering by status, priority, and search."
        ),
        parameters=[
            OpenApiParameter(
                "status",
                str,
                description="Filter by status (pending, started, in_progress, completed)",
            ),
            OpenApiParameter(
                "priority",
                str,
                description="Filter by priority (low, medium, high, urgent)",
            ),
            OpenApiParameter(
                "search", str, description="Search keyword in title or description"
            ),
            OpenApiParameter(
                "user_id",
                int,
                description="Admin only: Filter notes by specific user ID",
            ),
        ],
    )
    def get_queryset(self):
        user = self.request.user

        if user.role == "admin" or user.is_superuser:
            queryset = Note.objects.all().select_related("owner")
            user_id = self.request.query_params.get("user_id")
            if user_id:
                queryset = queryset.filter(owner_id=user_id)
        else:
            queryset = Note.objects.filter(owner=user)

        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param.lower())

        priority_param = self.request.query_params.get("priority")
        if priority_param:
            queryset = queryset.filter(priority=priority_param.lower())

        search_query = self.request.query_params.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class NoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific note.
    - Regular users can only access/modify their own notes.
    - Administrators can view any note.
    """

    serializer_class = NoteSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsVerifiedUser,
        IsOwnerOrAdminReadOnly,
    ]

    @extend_schema(
        summary="Retrieve, Update or Delete a Note",
        description="Retrieve, update (full/partial), or delete a specific note by ID with role authorization.",
    )
    def get_queryset(self):
        user = self.request.user
        if user.role == "admin" or user.is_superuser:
            return Note.objects.all().select_related("owner")
        return Note.objects.filter(owner=user)
