from rest_framework import serializers

from .models import AuditLog, SystemSetting


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "actor_name", "action", "details", "created_at"]
        read_only_fields = ["id", "created_at"]


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = ["id", "key", "value", "description"]
