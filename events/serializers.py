from rest_framework import serializers

from .models import Event, Visitor


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "event_code", "name", "date", "expected_visitors", "status", "description"]
        read_only_fields = ["id", "event_code"]


class VisitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visitor
        fields = ["id", "visitor_code", "name", "check_in", "check_out", "zone", "party_size", "status"]
        read_only_fields = ["id", "visitor_code", "check_in"]
