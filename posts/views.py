from collections import defaultdict
from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response

from .models import Post, PostPrivacy, PostReaction
from .permissions import IsAuthorOrAdmin
from .serializers import (
    GroupedInterestUserSerializer,
    PostCreateUpdateSerializer,
    PostSerializer,
    ReactActionSerializer,
)
from accounts.permissions import IsVerifiedUser

User = get_user_model()


class PostListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        if self.request.method == "POST":
            return PostCreateUpdateSerializer
        return PostSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsVerifiedUser()]
        return [permissions.AllowAny()]

    @extend_schema(
        tags=["posts"],
        summary="List Posts",
        description="Retrieves a paginated list of posts with author details and reaction counts. Unauthenticated visitors see public posts; logged-in users see both public and in-app posts.",
        parameters=[
            OpenApiParameter("privacy", str, description="Filter by privacy: public or authenticated"),
            OpenApiParameter("author_id", int, description="Filter posts by author user ID"),
            OpenApiParameter("search", str, description="Search keyword within post caption or author email"),
        ],
        responses={200: PostSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["posts"],
        summary="Create Post",
        description="Creates a new post with a caption and privacy level (public or authenticated). Requires verified user authentication.",
        request=PostCreateUpdateSerializer,
        responses={
            201: PostSerializer,
            400: OpenApiResponse(description="Validation error in submitted post data."),
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        queryset = Post.objects.select_related("author")

        if not user.is_authenticated:
            queryset = queryset.filter(privacy=PostPrivacy.PUBLIC)

        privacy_param = self.request.query_params.get("privacy")
        if privacy_param:
            queryset = queryset.filter(privacy=privacy_param.lower())

        author_id = self.request.query_params.get("author_id")
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        search_query = self.request.query_params.get("search")
        if search_query:
            queryset = queryset.filter(
                Q(caption__icontains=search_query) | Q(author__email__icontains=search_query)
            )

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.select_related("author")

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return PostCreateUpdateSerializer
        return PostSerializer

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [permissions.IsAuthenticated(), IsVerifiedUser(), IsAuthorOrAdmin()]
        return [permissions.AllowAny()]

    @extend_schema(
        tags=["posts"],
        summary="Get Post Details",
        description="Retrieves details of a specific post including author info and reaction status.",
        responses={
            200: PostSerializer,
            403: OpenApiResponse(description="Post is restricted to authenticated members."),
            404: OpenApiResponse(description="Post not found."),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["posts"],
        summary="Full Update Post",
        description="Updates caption or privacy settings of an existing post. Only the post author or an administrator can perform this action.",
        request=PostCreateUpdateSerializer,
        responses={
            200: PostSerializer,
            403: OpenApiResponse(description="Permission denied."),
            404: OpenApiResponse(description="Post not found."),
        },
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        tags=["posts"],
        summary="Partial Update Post",
        description="Partially updates caption or privacy level of an existing post. Only the post author or an administrator can perform this action.",
        request=PostCreateUpdateSerializer,
        responses={
            200: PostSerializer,
            403: OpenApiResponse(description="Permission denied."),
            404: OpenApiResponse(description="Post not found."),
        },
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        tags=["posts"],
        summary="Delete Post",
        description="Permanently deletes a specific post. Only the post author or an administrator can perform this action.",
        responses={
            204: OpenApiResponse(description="Post deleted successfully."),
            403: OpenApiResponse(description="Permission denied."),
            404: OpenApiResponse(description="Post not found."),
        },
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def get_object(self):
        post = super().get_object()
        if post.privacy == PostPrivacy.AUTHENTICATED and not self.request.user.is_authenticated:
            self.permission_denied(
                self.request,
                message="This post is restricted to in-app authenticated members."
            )
        return post


class PostReactToggleView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsVerifiedUser]

    @extend_schema(
        tags=["posts"],
        summary="Toggle Post Reaction",
        description="Adds a reaction (e.g. like, love, clap) to a post, or removes it if already reacted with the same type. Keeps reaction count accurate.",
        request=ReactActionSerializer,
        responses={
            200: OpenApiResponse(
                description="Reaction toggled successfully.",
                response={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "reacted": {"type": "boolean"},
                        "react_count": {"type": "integer"},
                    },
                },
            ),
            404: OpenApiResponse(description="Post not found."),
        },
    )
    def post(self, request, pk, *args, **kwargs):
        try:
            post = Post.objects.get(pk=pk)
        except Post.DoesNotExist:
            return Response({"detail": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReactActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reaction_type = serializer.validated_data.get("reaction_type", "like")

        reaction = PostReaction.objects.filter(post=post, user=request.user).first()
        if reaction:
            if reaction.reaction_type == reaction_type:
                reaction.delete()
                reacted = False
            else:
                reaction.reaction_type = reaction_type
                reaction.save()
                reacted = True
        else:
            PostReaction.objects.create(post=post, user=request.user, reaction_type=reaction_type)
            reacted = True

        post.react_count = post.reactions.count()
        post.save(update_fields=["react_count"])

        return Response(
            {
                "success": True,
                "reacted": reacted,
                "react_count": post.react_count,
            },
            status=status.HTTP_200_OK,
        )


class UserPostsLookupView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["posts"],
        summary="Get Posts by User",
        description="Retrieves all posts belonging to a particular user with author details. Supports query indexing and pagination.",
        responses={200: PostSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        user_id = self.kwargs.get("user_id")
        queryset = Post.objects.filter(author_id=user_id).select_related("author")

        if not self.request.user.is_authenticated:
            queryset = queryset.filter(privacy=PostPrivacy.PUBLIC)

        return queryset.order_by("-created_at")


class GroupByInterestsView(views.APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["posts"],
        summary="Group Users by Interests",
        description="Retrieves user profiles grouped and indexed by their registered interests list.",
        responses={200: GroupedInterestUserSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        users = (
            User.objects.filter(is_active=True)
            .exclude(interests=[])
            .only("id", "email", "username", "interests")
        )

        interest_groups = defaultdict(list)
        for user in users:
            if isinstance(user.interests, list):
                for interest in user.interests:
                    cleaned_interest = str(interest).strip().lower()
                    if cleaned_interest:
                        interest_groups[cleaned_interest].append(
                            {
                                "id": user.id,
                                "email": user.email,
                                "username": user.username or user.email.split("@")[0],
                            }
                        )

        grouped_results = [
            {
                "interest": interest,
                "user_count": len(user_list),
                "users": user_list,
            }
            for interest, user_list in sorted(interest_groups.items(), key=lambda x: -len(x[1]))
        ]

        return Response(grouped_results, status=status.HTTP_200_OK)
