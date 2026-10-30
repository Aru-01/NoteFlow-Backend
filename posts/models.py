from django.conf import settings
from django.db import models


class PostPrivacy(models.TextChoices):
    PUBLIC = "public", "Public (Any user)"
    AUTHENTICATED = "authenticated", "In-App (Authenticated users only)"


class Post(models.Model):
    """
    Post model representing user shared content with privacy control,
    reactions, and query indexing per interview specifications.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
        db_index=True,
        help_text="User who authored this post",
    )
    caption = models.TextField(
        help_text="Caption or body text of the post",
    )
    privacy = models.CharField(
        max_length=20,
        choices=PostPrivacy.choices,
        default=PostPrivacy.PUBLIC,
        db_index=True,
        help_text="Visibility: public for everyone or authenticated for in-app users",
    )
    react_count = models.PositiveIntegerField(
        default=0,
        help_text="Aggregated number of reactions received on this post",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the post was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the post was last modified",
    )

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["privacy", "-created_at"]),
        ]

    def __str__(self):
        return f"Post by {self.author.email}: {self.caption[:30]}"


class PostReaction(models.Model):
    """
    Records reactions from authenticated users, preventing duplicate reactions
    and keeping react_count accurate.
    """

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="reactions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_reactions",
    )
    reaction_type = models.CharField(
        max_length=20,
        default="like",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")
        verbose_name = "Post Reaction"
        verbose_name_plural = "Post Reactions"

    def __str__(self):
        return (
            f"{self.user.email} reacted '{self.reaction_type}' to Post {self.post_id}"
        )
