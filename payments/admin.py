# payments/admin.py
from django.contrib import admin
from .models import SevaPayment


@admin.register(SevaPayment)
class SevaPaymentAdmin(admin.ModelAdmin):
    list_display = ("seva_name", "amount", "currency", "razorpay_order_id",
                     "razorpay_payment_id", "payment_status", "created_at")
    list_filter = ("payment_status", "currency")
    search_fields = ("seva_name", "razorpay_order_id", "razorpay_payment_id")
    readonly_fields = ("id", "created_at", "updated_at")