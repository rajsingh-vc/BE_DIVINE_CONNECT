from decimal import Decimal

from rest_framework import serializers

from devotees.models import Devotee

from .models import Donation


class DonationSerializer(serializers.ModelSerializer):
    """Full donation record — used by the admin console (list/retrieve/CRUD)."""

    devotee_name = serializers.CharField(source="devotee.full_name", read_only=True, default=None)
    bill_summary = serializers.SerializerMethodField()

    class Meta:
        model = Donation
        fields = [
            "id", "donation_code", "devotee", "devotee_name",
            # amount
            "amount", "is_anonymous",
            # donor information
            "donor_name", "donor_email", "donor_mobile", "donor_address",
            # tax & receipt (optional)
            "want_80g_receipt", "donor_pan", "receipt_number",
            "purpose",
            # bill summary figures
            "platform_fee", "total_amount",
            # payment
            "payment_status", "payment_reference", "created_at", "paid_at",
            "bill_summary",
        ]
        read_only_fields = [
            "id", "donation_code", "platform_fee", "total_amount", "receipt_number",
            "payment_status", "payment_reference", "created_at", "paid_at", "bill_summary",
        ]

    def get_bill_summary(self, obj):
        return obj.bill_summary

    def validate(self, attrs):
        is_anonymous = attrs.get("is_anonymous", getattr(self.instance, "is_anonymous", False))
        donor_name = attrs.get("donor_name", getattr(self.instance, "donor_name", ""))
        if not is_anonymous and not donor_name:
            raise serializers.ValidationError({"donor_name": "Donor name is required unless donating anonymously."})

        want_receipt = attrs.get("want_80g_receipt", getattr(self.instance, "want_80g_receipt", False))
        donor_pan = attrs.get("donor_pan", getattr(self.instance, "donor_pan", ""))
        if want_receipt and not donor_pan:
            raise serializers.ValidationError({"donor_pan": "PAN is required to issue an 80G tax receipt."})
        return attrs


class GenerateDonationSerializer(serializers.Serializer):
    """Input for POST /api/donations/generate/ — the donation form:
    amount (+ anonymous toggle), donor information, and an optional
    tax/80G receipt request. Creates a pending Donation + Razorpay order."""

    devotee = serializers.PrimaryKeyRelatedField(queryset=Devotee.objects.all(), required=False, allow_null=True)

    # --- Amount ---
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("1"))
    is_anonymous = serializers.BooleanField(default=False)

    # --- Donor information ---
    donor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    donor_email = serializers.EmailField(required=False, allow_blank=True, default="")
    donor_mobile = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    donor_address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    # --- Tax & receipt (optional) ---
    want_80g_receipt = serializers.BooleanField(default=False)
    donor_pan = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")

    purpose = serializers.ChoiceField(choices=Donation.Purpose.choices, default=Donation.Purpose.GENERAL)

    def validate(self, attrs):
        if not attrs.get("is_anonymous") and not attrs.get("donor_name"):
            raise serializers.ValidationError({"donor_name": "Donor name is required unless donating anonymously."})
        if attrs.get("want_80g_receipt") and not attrs.get("donor_pan"):
            raise serializers.ValidationError({"donor_pan": "PAN is required to issue an 80G tax receipt."})
        return attrs