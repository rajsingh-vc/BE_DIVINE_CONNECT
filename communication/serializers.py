from rest_framework import serializers

from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "title", "message", "channel", "audience", "sent_at", "created_at"]
        read_only_fields = ["id", "created_at"]
