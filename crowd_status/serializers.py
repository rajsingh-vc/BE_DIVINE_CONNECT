# crowd_status/serializers.py — FULL FILE
from rest_framework import serializers

from .models import Attendance, CrowdStatus, CrowdThresholds, MealCollection, ScanHistory

from .models import ManualCounter  # add ManualCounter to the existing models import line instead

from .models import Attendance, CrowdStatus, CrowdThresholds, MealCollection, ScanHistory, VolunteerAreaAssignment

class ScanQRRequestSerializer(serializers.Serializer):
    """Shared by both QR types — Flutter always posts the same shape
    regardless of whether it scanned the Entry QR or the Meal QR; the
    backend is what tells them apart."""
    encrypted_data = serializers.CharField()


class VerifyVolunteerRequestSerializer(serializers.Serializer):
    encrypted_data = serializers.CharField()


class ManualCheckinRequestSerializer(serializers.Serializer):
    volunteer_token = serializers.CharField(
        help_text="The encrypted_data string that was just verified by /verify-volunteer/. "
                   "Sent again here so this endpoint can't be called without that step."
    )
    devotee_id = serializers.IntegerField(required=False)
    booking_reference = serializers.CharField(required=False, allow_blank=True)
    mobile = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True)
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not any([attrs.get("devotee_id"), attrs.get("booking_reference"), attrs.get("mobile"), attrs.get("name")]):
            raise serializers.ValidationError("Provide at least one of devotee_id, booking_reference, mobile, or name.")
        return attrs


class AttendanceSerializer(serializers.ModelSerializer):
    devotee_name = serializers.CharField(source="devotee.full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = ["id", "devotee", "devotee_name", "volunteer", "check_type", "scan_method",
                   "booking_reference", "location", "timestamp", "status", "remarks"]
        read_only_fields = fields


class ScanHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanHistory
        fields = ["id", "user_type", "devotee", "volunteer", "scan_method", "action_type",
                   "booking_reference", "scan_time", "scan_status", "device_ip", "response_message"]
        read_only_fields = fields


class MealCollectionSerializer(serializers.ModelSerializer):
    devotee_name = serializers.CharField(source="devotee.full_name", read_only=True)

    class Meta:
        model = MealCollection
        fields = ["id", "devotee", "devotee_name", "volunteer", "location", "timestamp", "status"]
        read_only_fields = fields


class DevoteeQRCardSerializer(serializers.Serializer):
    """Shape of a single card on the devotee's 'My QR' screen — used only
    for documenting/validating the response shape, not for parsing input."""
    label = serializers.CharField()
    purpose = serializers.CharField()
    qr_data = serializers.CharField()
    qr_image = serializers.CharField()


class CrowdStatusSerializer(serializers.ModelSerializer):
    """Admin-facing read/write serializer — includes who last updated it."""

    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CrowdStatus
        fields = [
            "id",
            "assigned_area",
            "crowd_level",
            "approx_visitors",
            "wait_time",
            "updated_by",
            "updated_by_name",
            "timestamp",
            "status",
        ]
        read_only_fields = ["id", "updated_by", "updated_by_name", "timestamp"]

    def get_updated_by_name(self, obj):
        if not obj.updated_by:
            return None
        return obj.updated_by.get_full_name() or getattr(obj.updated_by, "username", None)


class VolunteerCrowdStatusSerializer(serializers.ModelSerializer):
    """Used when a volunteer submits their own area's status.

    `assigned_area` is deliberately excluded — the view sets it from the
    volunteer's assignment, never from client input, so a volunteer can't
    report on someone else's area.
    """

    class Meta:
        model = CrowdStatus
        fields = ["id", "assigned_area", "crowd_level", "approx_visitors", "wait_time", "status", "timestamp"]
        read_only_fields = ["id", "assigned_area", "timestamp"]


class CrowdThresholdsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrowdThresholds
        fields = ["low_max", "moderate_max"]

    def validate(self, attrs):
        low = attrs.get("low_max", getattr(self.instance, "low_max", None))
        moderate = attrs.get("moderate_max", getattr(self.instance, "moderate_max", None))
        if low is not None and moderate is not None and moderate <= low:
            raise serializers.ValidationError({"moderate_max": "Must be greater than low_max."})
        return attrs




class ManualCounterRequestSerializer(serializers.Serializer):
    """Body for POST /api/manual-counter/. `action` is the human word the
    Flutter app sends ("increment"/"decrement"); the view maps it onto
    ManualCounter.INCREMENT/DECREMENT."""
    action = serializers.ChoiceField(choices=["increment", "decrement"])
    count = serializers.IntegerField(min_value=1, default=1)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ManualCounterSerializer(serializers.ModelSerializer):
    """Audit-log shape — used for the admin list."""
    volunteer_name = serializers.SerializerMethodField()

    class Meta:
        model = ManualCounter
        fields = ["id", "volunteer", "volunteer_name", "assigned_area", "action", "count", "reason", "timestamp"]
        read_only_fields = fields

    def get_volunteer_name(self, obj):
        if not obj.volunteer:
            return None
        return obj.volunteer.get_full_name() or getattr(obj.volunteer, "username", None)


class ManualCounterSummarySerializer(serializers.Serializer):
    """Shape of GET /api/manual-counter/ — documents the response, not
    used for input parsing."""
    current_manual_count = serializers.IntegerField()
    today_increment = serializers.IntegerField()
    today_decrement = serializers.IntegerField()

class VolunteerAreaAssignmentSerializer(serializers.ModelSerializer):
    """Read shape for GET /api/admin/volunteer-areas/ — one row per
    assignment, with volunteer identity flattened in for the admin list."""
    volunteer_id = serializers.IntegerField(source="volunteer.id", read_only=True)
    volunteer_name = serializers.SerializerMethodField()
    volunteer_username = serializers.CharField(source="volunteer.username", read_only=True)

    class Meta:
        model = VolunteerAreaAssignment
        fields = ["id", "volunteer_id", "volunteer_name", "volunteer_username", "assigned_area"]
        read_only_fields = fields

    def get_volunteer_name(self, obj):
        return obj.volunteer.get_full_name() or getattr(obj.volunteer, "username", None)


class VolunteerAreaAssignmentUpsertSerializer(serializers.Serializer):
    """Body for POST /api/admin/volunteer-areas/. assigned_area allows
    blank on purpose — the view treats a blank value as 'remove this
    volunteer's assignment' rather than a validation error."""
    volunteer_id = serializers.IntegerField()
    assigned_area = serializers.CharField(allow_blank=True, required=True)