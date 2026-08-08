from rest_framework import serializers

from .models import InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id", "sku", "item_name", "stock", "min_threshold", "unit",
            "dispatched_today", "open_purchase_orders", "status", "updated_at",
        ]
        read_only_fields = ["id", "updated_at", "status"]