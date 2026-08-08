from rest_framework import serializers

from .models import IncidentReport


class IncidentReportSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    reported_by_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()

    # "Awaiting Response" -> "Responded", driven purely by whether an admin
    # has written anything into resolution_notes. Independent of `status`.
    response_status = serializers.SerializerMethodField()
    response_status_display = serializers.SerializerMethodField()

    class Meta:
        model = IncidentReport
        fields = [
            "id",
            "incident_code",
            "title",
            "category",
            "category_display",
            "severity",
            "severity_display",
            "status",
            "status_display",
            "description",
            "image",
            "location",
            "reported_by",
            "reported_by_name",
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
            "incident_code",
            "reported_by",
            "reported_by_name",
            "resolved_by",
            "resolved_by_name",
            "responded_at",
            "response_status",
            "response_status_display",
            "created_at",
            "updated_at",
        ]

    def get_reported_by_name(self, obj):
        return obj.reported_by.full_name if obj.reported_by else "Unknown"

    def get_resolved_by_name(self, obj):
        return obj.resolved_by.full_name if obj.resolved_by else ""

    def get_response_status(self, obj):
        return obj.response_status

    def get_response_status_display(self, obj):
        return "Responded" if obj.response_status == "responded" else "Awaiting Response"