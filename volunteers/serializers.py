from rest_framework import serializers
from .models import Volunteer, Verification, VolunteerApproval, Notification, AuditLog, VolunteerIdSequence, Duty

from rest_framework import serializers
from .models import MealSession, MealCheckIn


class MealSessionSerializer(serializers.ModelSerializer):
    is_open = serializers.SerializerMethodField()
    meal_name_display = serializers.CharField(source="get_meal_name_display", read_only=True)

    class Meta:
        model = MealSession
        fields = [
            "id", "session_code", "meal_name", "meal_name_display", "location", "start_time", "end_time",
            "is_active", "is_open", "created_at",
        ]
        read_only_fields = ["session_code", "created_at"]

    def get_is_open(self, obj):
        return obj.is_open()


class MealCheckInSerializer(serializers.ModelSerializer):
    volunteer_name = serializers.CharField(source="volunteer.full_name", read_only=True)
    volunteer_code = serializers.CharField(source="volunteer.volunteer_code", read_only=True, default="")
    location = serializers.CharField(source="session.location", read_only=True)
    session_code = serializers.CharField(source="session.session_code", read_only=True)
    # NEW — which meal this check-in belongs to, so the scan result can show
    # name/id/meal-type/entry-status together without a second lookup.
    meal_name = serializers.CharField(source="session.meal_name", read_only=True)
    meal_name_display = serializers.CharField(source="session.get_meal_name_display", read_only=True)

    class Meta:
        model = MealCheckIn
        fields = [
            "id", "checkin_code", "session", "session_code", "location",
            "volunteer", "volunteer_name", "volunteer_code",
            "meal_name", "meal_name_display",
            "assigned_role", "shift_timing", "status",
            "check_in_time", "check_out_time", "scan_count", "created_at",
        ]
        read_only_fields = fields


class DutySerializer(serializers.ModelSerializer):
    volunteer_name = serializers.CharField(source="volunteer.name", read_only=True)
    volunteer_code = serializers.CharField(source="volunteer.volunteer_code", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True, default="")
    swap_requested_with_name = serializers.CharField(source="swap_requested_with.name", read_only=True, default="")

    class Meta:
        model = Duty
        fields = [
            "id", "duty_code", "volunteer", "volunteer_name", "volunteer_code",
            "title", "instructions", "location", "duty_date", "time",
            "priority", "status", "help_note",
            "swap_requested_with", "swap_requested_with_name", "swap_requested_at",
            "created_by", "created_by_name",
            "accepted_at", "started_at", "completed_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "duty_code", "status", "help_note", "created_by",
            "swap_requested_with", "swap_requested_at",
            "accepted_at", "started_at", "completed_at", "created_at", "updated_at",
        ]


class DutyAssignSerializer(serializers.Serializer):
    """Admin payload: assign one duty to one or more volunteers at once."""
    volunteer_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    title = serializers.CharField(max_length=200)
    instructions = serializers.CharField(required=False, allow_blank=True, default="")
    location = serializers.CharField(required=False, allow_blank=True, default="")
    duty_date = serializers.DateField()
    time = serializers.TimeField(required=False, allow_null=True)
    priority = serializers.ChoiceField(choices=Duty.Priority.choices, default=Duty.Priority.NORMAL)


class DutyHelpSerializer(serializers.Serializer):
    """Payload for the 'Swap / help' button.
    - swap_with omitted or null -> plain help request (status=help_requested)
    - swap_with set -> swap request to that specific volunteer,
      populated from a dropdown (status=swap_requested)
    """
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    swap_with = serializers.PrimaryKeyRelatedField(
        queryset=Volunteer.objects.filter(is_volunteer=True, status=Volunteer.Status.ADMIN_APPROVED),
        required=False,
        allow_null=True,
    )


class DutySwapResponseSerializer(serializers.Serializer):
    """Payload for the target volunteer accepting/declining a swap."""
    action = serializers.ChoiceField(choices=["accept", "decline"])


class SwapCandidateSerializer(serializers.ModelSerializer):
    """Powers the 'select name from dropdown' list on the Swap screen."""
    class Meta:
        model = Volunteer
        fields = ["id", "name", "volunteer_code", "public_id"]


class VerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verification
        fields = [
            "aadhaar_number", "aadhaar_front", "aadhaar_back",
            "pan_number", "pan_front", "pan_back",
            "license_number", "license_front", "license_back",
            "live_photo",
        ]


class VolunteerApprovalSerializer(serializers.ModelSerializer):
    time_remaining_seconds = serializers.IntegerField(read_only=True)
    reference_volunteer_name = serializers.CharField(source="reference_volunteer.name", read_only=True)

    class Meta:
        model = VolunteerApproval
        fields = [
            "id", "reference_volunteer", "reference_volunteer_name", "reference_comment",
            "reference_status", "reference_action_at",
            "admin_status", "admin_action_at", "admin_action_by",
            "auto_rejected", "deadline", "time_remaining_seconds", "created_at",
        ]
        read_only_fields = ["reference_action_at", "admin_action_at", "admin_action_by", "auto_rejected", "deadline"]


class VolunteerListSerializer(serializers.ModelSerializer):
    reference_volunteer_name = serializers.CharField(source="reference_volunteer.name", read_only=True, default="")
    approval = VolunteerApprovalSerializer(read_only=True)

    class Meta:
        model = Volunteer
        fields = [
            "id", "volunteer_code", "public_id", "name", "email", "phone", "profile_photo",
            "is_volunteer", "status", "reference_volunteer", "reference_volunteer_name",
            "approval", "created_at",
        ]


class VolunteerDetailSerializer(serializers.ModelSerializer):
    verification = VerificationSerializer(read_only=True)
    approval = VolunteerApprovalSerializer(read_only=True)

    class Meta:
        model = Volunteer
        fields = [
            "id", "volunteer_code", "public_id", "name", "email", "phone", "profile_photo",
            "is_volunteer", "status", "reference_volunteer", "created_by",
            "verification", "approval", "created_at", "updated_at",
        ]


class VolunteerRegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    profile_photo = serializers.ImageField(required=False)

    aadhaar_number = serializers.CharField(required=False, allow_blank=True)
    aadhaar_front = serializers.ImageField(required=False)
    aadhaar_back = serializers.ImageField(required=False)
    pan_number = serializers.CharField(required=False, allow_blank=True)
    pan_front = serializers.ImageField(required=False)
    pan_back = serializers.ImageField(required=False)
    license_number = serializers.CharField(required=False, allow_blank=True)
    license_front = serializers.ImageField(required=False)
    license_back = serializers.ImageField(required=False)
    live_photo = serializers.ImageField(required=False)

    reference_comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")

    reference_volunteer = serializers.PrimaryKeyRelatedField(
        queryset=Volunteer.objects.filter(status=Volunteer.Status.ADMIN_APPROVED),
        required=False,
        allow_null=True,
    )


class VolunteerApplySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)

    document_front = serializers.ImageField()
    document_back = serializers.ImageField(required=False)
    document_number = serializers.CharField(required=False, allow_blank=True, default="")

    selfie = serializers.ImageField()

    reference_volunteer = serializers.PrimaryKeyRelatedField(
        queryset=Volunteer.objects.filter(status=Volunteer.Status.ADMIN_APPROVED),
        required=False,
        allow_null=True,
    )


class ReferenceActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])


class AdminActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    override = serializers.BooleanField(required=False, default=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "type", "related_volunteer", "is_read", "created_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True, default="")

    class Meta:
        model = AuditLog
        fields = ["id", "action", "actor", "actor_name", "detail", "created_at"]

class MealSelfCheckInSerializer(serializers.Serializer):
    """Volunteer-supplied fields when they tap 'Meal'."""
    location = serializers.CharField(max_length=100)
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    def validate(self, data):
        if data["end_time"] <= data["start_time"]:
            raise serializers.ValidationError("end_time must be after start_time.")
        return data