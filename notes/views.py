from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from .models import Note
from .permissions import IsOwnerOrAdminReadOnly
from .serializers import NoteSerializer
from accounts.permissions import IsVerifiedUser


class NoteListCreateView(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsVerifiedUser]

    @extend_schema(
        tags=["notes"],
        summary="List Notes",
        description="Retrieves a paginated list of notes. Regular users only see their own notes. Administrators can view all notes or filter by specific user.",
        parameters=[
            OpenApiParameter(
                "status",
                str,
                description="Filter by lifecycle status (pending, started, in_progress, completed)",
            ),
            OpenApiParameter(
                "priority",
                str,
                description="Filter by priority level (low, medium, high, urgent)",
            ),
            OpenApiParameter(
                "search",
                str,
                description="Search keyword within note title or description",
            ),
            OpenApiParameter(
                "user_id",
                int,
                description="Admin only: Filter notes belonging to a specific user ID",
            ),
        ],
        responses={200: NoteSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["notes"],
        summary="Create Note",
        description="Creates a new note with title, description, priority, lifecycle status, and optional start/end timeframe. Ownership is automatically assigned to the authenticated user.",
        request=NoteSerializer,
        responses={
            201: NoteSerializer,
            400: OpenApiResponse(description="Validation error such as approx_end_date earlier than start_date."),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

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
    serializer_class = NoteSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsVerifiedUser,
        IsOwnerOrAdminReadOnly,
    ]

    @extend_schema(
        tags=["notes"],
        summary="Get Note Details",
        description="Retrieves full details of a specific note by ID. Accessible by the note owner or an administrator.",
        responses={
            200: NoteSerializer,
            404: OpenApiResponse(description="Note not found or you do not have permission to view it."),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["notes"],
        summary="Full Update Note",
        description="Updates all fields of an existing note. Accessible by the note owner or an administrator.",
        request=NoteSerializer,
        responses={
            200: NoteSerializer,
            400: OpenApiResponse(description="Validation error in submitted fields."),
            404: OpenApiResponse(description="Note not found."),
        },
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        tags=["notes"],
        summary="Partial Update Note",
        description="Updates one or more fields (e.g. status, priority, or dates) of an existing note.",
        request=NoteSerializer,
        responses={
            200: NoteSerializer,
            400: OpenApiResponse(description="Validation error in submitted fields."),
            404: OpenApiResponse(description="Note not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        tags=["notes"],
        summary="Delete Note",
        description="Permanently deletes a specific note by ID. Accessible by the note owner or an administrator.",
        responses={
            204: OpenApiResponse(description="Note deleted successfully."),
            404: OpenApiResponse(description="Note not found."),
        },
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin" or user.is_superuser:
            return Note.objects.all().select_related("owner")
        return Note.objects.filter(owner=user)
