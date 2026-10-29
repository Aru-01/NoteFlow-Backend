from django.conf import settings
from django.db import models


class NotePriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class NoteStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    STARTED = "started", "Started"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"


class Note(models.Model):
    """
    Note model with priority, lifecycle status, timeframe tracking,
    and optimized indexes for list and read operations.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
        db_index=True,
        help_text="User who owns this note",
    )
    title = models.CharField(
        max_length=200,
        help_text="Short title of the note",
    )
    description = models.TextField(
        blank=True,
        help_text="Brief / detailed description of the note",
    )
    priority = models.CharField(
        max_length=15,
        choices=NotePriority.choices,
        default=NotePriority.MEDIUM,
        db_index=True,
        help_text="Priority level (low, medium, high, urgent)",
    )
    status = models.CharField(
        max_length=20,
        choices=NoteStatus.choices,
        default=NoteStatus.PENDING,
        db_index=True,
        help_text="Current note status (pending, started, in_progress, completed)",
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Planned or actual start date",
    )
    approx_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Estimated completion or deadline date",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the note was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the note was last updated",
    )

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.status}) - {self.owner.email}"
