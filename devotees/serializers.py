from rest_framework import serializers

from .models import Devotee


class DevoteeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name")

    class Meta:
        model = Devotee
        fields = [
            "id", "devotee_code", "name", "email", "mobile", "city",
            "tier", "guest_count", "visits", "total_donated", "created_at", "user",
        ]
        read_only_fields = ["id", "devotee_code", "created_at"]
        extra_kwargs = {"user": {"required": False, "allow_null": True}}


class DevoteeRegistrationSerializer(serializers.ModelSerializer):
    """Powers the 'Online Seva Booking' form and its /lookup/ + /register/
    actions on DevoteeViewSet. Kept separate from DevoteeSerializer above so
    nothing about the existing admin Devotees console (its `name` field,
    required-ness, or endpoints) changes.

    Also powers the VIP quick-add flow (name + guest count only), via the
    `is_vip` context flag — see __init__ below and
    DevoteeViewSet.register() in views.py, which sets that context."""

    referred_by_volunteer_code = serializers.CharField(
        source="referred_by_volunteer.volunteer_code", read_only=True, default=None
    )
    referred_by_volunteer_name = serializers.CharField(
        source="referred_by_volunteer.name", read_only=True, default=None
    )

    class Meta:
        model = Devotee
        fields = [
            "id", "devotee_code", "full_name",
            "first_name", "middle_name", "last_name",
            "mobile", "whatsapp", "email",
            "address", "city", "pincode", "pan_number",
            "referred_by_volunteer", "referred_by_volunteer_code", "referred_by_volunteer_name",
            "tier", "guest_count",
        ]
        read_only_fields = ["id", "devotee_code", "full_name", "tier"]
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
            "mobile": {"required": True},
            "whatsapp": {"required": True},
            "email": {"required": True},
            "address": {"required": True},
            "city": {"required": True},
            "pincode": {"required": True},
            "guest_count": {"required": False, "allow_null": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("is_vip"):
            for field_name in ("mobile", "whatsapp", "email", "address", "city", "pincode"):
                field = self.fields.get(field_name)
                if field is None:
                    continue
                field.required = False
                if hasattr(field, "allow_blank"):
                    field.allow_blank = True