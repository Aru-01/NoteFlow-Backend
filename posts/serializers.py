from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Post, PostPrivacy, PostReaction

User = get_user_model()


class AuthorSummarySerializer(serializers.ModelSerializer):
    """
    Lightweight author serializer embedded in posts.
    """

    class Meta:
        model = User
        fields = ("id", "email", "username", "interests")


class PostSerializer(serializers.ModelSerializer):
    """
    Serializer for displaying posts with full author metadata,
    privacy status, and reaction information.
    """

    author = AuthorSummarySerializer(read_only=True)
    has_reacted = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "caption",
            "privacy",
            "react_count",
            "has_reacted",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "author",
            "react_count",
            "has_reacted",
            "created_at",
            "updated_at",
        )

    def get_has_reacted(self, obj) -> bool:
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            if hasattr(obj, "_user_has_reacted"):
                return obj._user_has_reacted
            return obj.reactions.filter(user=request.user).exists()
        return False


class PostCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating post captions and privacy settings.
    """

    class Meta:
        model = Post
        fields = ("id", "caption", "privacy")
        read_only_fields = ("id",)


class ReactActionSerializer(serializers.Serializer):
    """
    Serializer for sending a reaction to a post.
    """

    reaction_type = serializers.CharField(
        max_length=20,
        default="like",
        required=False,
        help_text="Type of reaction (e.g., like, love, clap)",
    )


class GroupedInterestUserSerializer(serializers.Serializer):


    interest = serializers.CharField()
    user_count = serializers.IntegerField()
    users = serializers.ListField(child=serializers.DictField())
