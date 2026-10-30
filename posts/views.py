from collections import defaultdict
from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
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
    """
    List & Create Posts.
    - Public posts are visible to any user (including anonymous).
    - In-App (authenticated) posts are visible to logged-in users.
    - Creating a post requires an authenticated and verified account.
    """
    def get_serializer_class(self):
        if self.request.method == "POST":
            return PostCreateUpdateSerializer
        return PostSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsVerifiedUser()]
        return [permissions.AllowAny()]

    @extend_schema(
        summary="List Posts or Create a Post",
        description=(
            "List posts with author details and pagination. Unauthenticated visitors "
            "can read public posts; authenticated users can also read in-app posts."
        ),
        parameters=[
            OpenApiParameter("privacy", str, description="Filter by privacy: public or authenticated"),
            OpenApiParameter("author_id", int, description="Filter posts by author ID"),
            OpenApiParameter("search", str, description="Search keyword in post caption"),
        ],
    )
    def get_queryset(self):
        user = self.request.user
        queryset = Post.objects.select_related("author")

        # Privacy  filter
        if user.is_authenticated:
            pass
        else:
            queryset = queryset.filter(privacy=PostPrivacy.PUBLIC)

        # Query filter
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
    """
    Retrieve, update, or delete a specific post.
    Authors and Admins can update/delete. Any authorized viewer can retrieve.
    """
    queryset = Post.objects.select_related("author")

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return PostCreateUpdateSerializer
        return PostSerializer

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [permissions.IsAuthenticated(), IsVerifiedUser(), IsAuthorOrAdmin()]
        return [permissions.AllowAny()]

    def get_object(self):
        post = super().get_object()
        if post.privacy == PostPrivacy.AUTHENTICATED and not self.request.user.is_authenticated:
            self.permission_denied(
                self.request,
                message="This post is restricted to in-app authenticated members."
            )
        return post


class PostReactToggleView(views.APIView):
    """
    Toggle reaction on a post.
    If the user has already reacted with the given type, the reaction is removed.
    Otherwise, the reaction is recorded and react_count is kept accurate.
    """
    permission_classes = [permissions.IsAuthenticated, IsVerifiedUser]

    @extend_schema(
        summary="Toggle Reaction on Post",
        request=ReactActionSerializer,
        responses={200: PostSerializer},
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
    """
    Scenario 2 (Aggregation / Join Lookup):
    Retrieve all posts belonging to a particular user with joined author details.
    Uses an optimized single-query JOIN (select_related) backed by index (author, -created_at).
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Scenario 2: User Posts ($lookup Join)",
        description=(
            "Retrieves all posts belonging to a particular user. Executes an optimized single "
            "JOIN query with author metadata supported by composite index (author, -created_at)."
        ),
    )
    def get_queryset(self):
        user_id = self.kwargs.get("user_id")
        queryset = Post.objects.filter(author_id=user_id).select_related("author")

        if not self.request.user.is_authenticated:
            queryset = queryset.filter(privacy=PostPrivacy.PUBLIC)

        return queryset.order_by("-created_at")


class GroupByInterestsView(views.APIView):
    """
    Scenario 1 (Aggregation Task):
    Specific view to see users grouped by interests.
    Processes user interest arrays in an optimized grouping pipeline.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Scenario 1: Group Users by Interests",
        description="Aggregates and groups user profiles by their registered interests.",
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
