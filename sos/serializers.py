from rest_framework import serializers

from .models import SOSAlert


class SOSAlertSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source="get_alert_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    raised_by_name = serializers.SerializerMethodField()
    # Human-readable volunteer ID (e.g. "vol_12" / "VOL-4T7AJQ") resolved
    # server-side from the authenticated volunteer — never trust a
    # client-supplied volunteer id for who raised the alert.
    volunteer_id = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()

    # "Awaiting Response" -> "Responded", driven purely by whether an admin
    # has written anything into resolution_notes. Independent of `status`.
    response_status = serializers.SerializerMethodField()
    response_status_display = serializers.SerializerMethodField()

    class Meta:
        model = SOSAlert
        fields = [
            "id",
            "sos_code",
            "alert_type",
            "alert_type_display",
            "status",
            "status_display",
            "description",
            "image",
            "location",
            "latitude",
            "longitude",
            "raised_by",
            "raised_by_name",
            "volunteer_id",
            "resolved_by",
            "resolved_by_name",
            "resolution_notes",
            "responded_at",
            "response_status",
            "response_status_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "sos_code",
            "raised_by",
            "raised_by_name",
            "volunteer_id",
            "resolved_by",
            "resolved_by_name",
            "responded_at",
            "response_status",
            "response_status_display",
            "created_at",
            "updated_at",
        ]

    def get_raised_by_name(self, obj):
        return obj.raised_by.full_name if obj.raised_by else "Unknown"

    def get_volunteer_id(self, obj):
        if not obj.raised_by:
            return None
        profile = getattr(obj.raised_by, "volunteer_profile_v2", None)
        if not profile:
            return None
        return profile.public_id or profile.volunteer_code

    def get_resolved_by_name(self, obj):
        return obj.resolved_by.full_name if obj.resolved_by else ""

    def get_response_status(self, obj):
        return obj.response_status

    def get_response_status_display(self, obj):
        return "Responded" if obj.response_status == "responded" else "Awaiting Response"