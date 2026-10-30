from django.contrib import admin
from .models import Post, PostReaction


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "caption_preview",
        "privacy",
        "react_count",
        "created_at",
    )
    list_filter = ("privacy", "created_at")
    search_fields = ("caption", "author__email", "author__username")
    ordering = ("-created_at",)

    def caption_preview(self, obj):
        return obj.caption[:40] if obj.caption else ""

    caption_preview.short_description = "Caption"


@admin.register(PostReaction)
class PostReactionAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "reaction_type", "created_at")
    list_filter = ("reaction_type", "created_at")
    search_fields = ("post__caption", "user__email")
