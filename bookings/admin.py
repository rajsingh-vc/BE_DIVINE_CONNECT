from django.contrib import admin

from .models import Bill, Booking, Seva


@admin.register(Seva)
class SevaAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "capacity", "is_active", "is_popular")
    list_filter = ("category", "is_active", "is_popular")
    search_fields = ("name", "category")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("booking_code", "devotee", "seva", "date", "status", "amount")
    list_filter = ("status", "channel")
    search_fields = ("booking_code", "devotee__full_name")


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        "bill_number", "devotee", "seva", "amount", "volunteer",
        "created_by", "payment_status", "created_at",
    )
    list_filter = ("payment_status",)
    search_fields = ("bill_number", "invoice_number", "devotee__full_name", "seva__name")
    readonly_fields = ("bill_number", "invoice_number", "razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "created_at", "paid_at")