from rest_framework import serializers
from .models import Note

class NoteSerializer(serializers.ModelSerializer):
    """
    Serializer for creating, retrieving, and updating Notes.
    Owner is automatically populated from request user.
    """
    owner_id = serializers.ReadOnlyField(source="owner.id")
    owner_email = serializers.ReadOnlyField(source="owner.email")
    owner_username = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Note
        fields = (
            "id",
            "owner_id",
            "owner_email",
            "owner_username",
            "title",
            "description",
            "priority",
            "status",
            "start_date",
            "approx_end_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "owner_id", "owner_email", "owner_username", "created_at", "updated_at")

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        approx_end_date = attrs.get("approx_end_date")

        if self.instance:
            start_date = start_date if "start_date" in attrs else self.instance.start_date
            approx_end_date = approx_end_date if "approx_end_date" in attrs else self.instance.approx_end_date

        if start_date and approx_end_date and approx_end_date < start_date:
            raise serializers.ValidationError(
                {"approx_end_date": "Approximate end date cannot be earlier than start date."}
            )

        return attrs
