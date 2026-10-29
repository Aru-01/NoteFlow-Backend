from django.contrib import admin
from .models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "priority", "status", "start_date", "approx_end_date", "created_at")
    list_filter = ("priority", "status", "created_at")
    search_fields = ("title", "description", "owner__email", "owner__username")
    ordering = ("-created_at",)
