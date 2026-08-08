from rest_framework import serializers

from .models import Alert, LiveDarshan, LiveFestivalInfo

# =====================================================================
# ADD to dashboard/serializers.py
# (add `LiveDarshan` to the `from .models import ...` line at the top)
# =====================================================================
from .models import Alert, LiveDarshan, LiveFestivalInfo

class LiveDarshanSerializer(serializers.ModelSerializer):
    """Admin-only CRUD screen. Only `live_url` is required; `title` is
    optional and falls back to "Live Ganpati Darshan" via model.save()."""

    is_live_now = serializers.BooleanField(source="effective_is_live", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True, default="")

    class Meta:
        model = LiveDarshan
        fields = [
            "id", "title", "description", "live_url", "banner_image",
            "start_datetime", "end_datetime", "is_live", "is_live_now",
            "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
            "start_datetime": {"required": False, "allow_null": True},
            "end_datetime": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        start = attrs.get("start_datetime", getattr(self.instance, "start_datetime", None))
        end = attrs.get("end_datetime", getattr(self.instance, "end_datetime", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_datetime": "End time must be after start time."})
        return attrs


class LiveDarshanStatusSerializer(serializers.ModelSerializer):
    """Public GET /api/dashboard/live-darshan/ — polled by Admin/Volunteer/
    Devotee dashboards and the Flutter app. Matches the required shape:
    {"is_live": true, "id": 1, "title": "...", "live_url": "..."}"""

    is_live = serializers.BooleanField(source="effective_is_live", read_only=True)

    class Meta:
        model = LiveDarshan
        fields = ["is_live", "id", "title", "live_url", "description", "banner_image"]


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ["id", "alert_code", "severity", "category", "description", "is_active", "created_at"]
        read_only_fields = ["id", "alert_code", "created_at"]


class LiveFestivalInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiveFestivalInfo
        fields = [
            "id", "title", "start_time", "end_time", "description",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        return attrs