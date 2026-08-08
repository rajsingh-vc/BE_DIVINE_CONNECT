from django.contrib import admin

from .models import Donation


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = (
        "donation_code", "donor_display", "amount", "platform_fee", "total_amount",
        "purpose", "payment_status", "want_80g_receipt", "created_at",
    )
    list_filter = ("purpose", "is_anonymous", "payment_status", "want_80g_receipt")
    search_fields = ("donation_code", "donor_name", "donor_email", "donor_mobile", "receipt_number")
    readonly_fields = ("donation_code", "platform_fee", "total_amount", "receipt_number", "created_at", "paid_at")

    @admin.display(description="Donor")
    def donor_display(self, obj):
        return "Anonymous Donor" if obj.is_anonymous else (obj.donor_name or "—")