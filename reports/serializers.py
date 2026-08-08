from rest_framework import serializers

from .models import SavedReport


class SavedReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedReport
        fields = ["id", "name", "report_type", "generated_by", "generated_at", "parameters"]
        read_only_fields = ["id", "generated_by", "generated_at"]
