# payments/serializers.py
from rest_framework import serializers
from .models import SevaPayment


class CreateOrderSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=100)  # paise; min ₹1
    currency = serializers.CharField(max_length=10, default="INR")
    seva_name = serializers.CharField(max_length=255)


class VerifyPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField(max_length=100)
    razorpay_payment_id = serializers.CharField(max_length=100)
    razorpay_signature = serializers.CharField(max_length=255)
    seva_name = serializers.CharField(max_length=255)
    amount = serializers.IntegerField(min_value=1)


class SevaPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SevaPayment
        fields = ["id", "seva_name", "amount", "currency", "razorpay_order_id",
                  "razorpay_payment_id", "payment_status", "created_at"]