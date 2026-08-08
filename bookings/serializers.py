from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from crowd_status.qr_generator import render_qr_image
from devotees.models import Devotee
from volunteers.models import Volunteer

from .models import Bill, Booking, MealBooking, Seva


class SevaSerializer(serializers.ModelSerializer):
    is_live = serializers.BooleanField(read_only=True)
    is_bookable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Seva
        fields = [
            "id", "name", "category", "price", "duration_minutes",
            "slots_per_day", "capacity", "priest", "description", "is_active",
            "is_popular", "start_date", "start_time", "end_date", "end_time",
            "is_live", "is_bookable",
        ]

    # ------------------------------------------------------------------
    # Sec.2 — REAL backend validation. Never trust the frontend: this runs
    # no matter who/what calls POST/PATCH /api/sevas/.
    # ------------------------------------------------------------------
    def validate(self, attrs):
        def current(field):
            return attrs.get(field, getattr(self.instance, field, None))

        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        start_date, start_time = current("start_date"), current("start_time")
        end_date, end_time = current("end_date"), current("end_time")

        # A Seva that is (or is becoming) active/bookable MUST have a full,
        # valid schedule. Inactive/draft sevas are allowed to omit them.
        if is_active:
            errors = {}
            if not start_date:
                errors["start_date"] = ["Start date is required."]
            if not start_time:
                errors["start_time"] = ["Start time is required."]
            if not end_date:
                errors["end_date"] = ["End date is required."]
            if not end_time:
                errors["end_time"] = ["End time is required."]
            if errors:
                raise serializers.ValidationError(errors)

            start_dt = self._aware(start_date, start_time)
            end_dt = self._aware(end_date, end_time)
            if end_dt <= start_dt:
                raise serializers.ValidationError({
                    "end_date": ["End date/time must be after start date/time."],
                    "end_time": ["End date/time must be after start date/time."],
                })
        return attrs

    @staticmethod
    def _aware(date_val, time_val):
        naive = datetime.combine(date_val, time_val)
        tz = timezone.get_current_timezone()
        return timezone.make_aware(naive, tz) if timezone.is_naive(naive) else naive


class BookingSerializer(serializers.ModelSerializer):
    devotee_name = serializers.CharField(source="devotee.full_name", read_only=True)
    seva_name = serializers.CharField(source="seva.name", read_only=True)
    seva_description = serializers.CharField(source="seva.description", read_only=True)
    bill_number = serializers.CharField(source="bill.bill_number", read_only=True, default="")
    qr_image = serializers.SerializerMethodField()
    # Read live off the linked Seva (Sec.4/17) — never duplicated columns.
    seva_start_date = serializers.DateField(source="seva.start_date", read_only=True)
    seva_start_time = serializers.TimeField(source="seva.start_time", read_only=True)
    seva_end_date = serializers.DateField(source="seva.end_date", read_only=True)
    seva_end_time = serializers.TimeField(source="seva.end_time", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "booking_code", "devotee", "devotee_name", "seva", "seva_name",
            "seva_description", "seva_start_date", "seva_start_time",
            "seva_end_date", "seva_end_time",
            "date", "slot", "amount", "channel", "status", "created_at",
            "payment_id", "bill", "bill_number",
            "encrypted_qr", "qr_generated_at", "qr_scanned_at", "is_used", "qr_image",
        ]
        read_only_fields = [
            "id", "booking_code", "created_at", "payment_id", "bill", "bill_number",
            "encrypted_qr", "qr_generated_at", "qr_scanned_at", "is_used", "qr_image",
        ]

    def get_qr_image(self, obj):
        if not obj.encrypted_qr:
            return None
        return render_qr_image(obj.encrypted_qr)

    # ------------------------------------------------------------------
    # Sec.3/19 — server-side booking-window enforcement. Runs on CREATE
    # regardless of what the frontend sent; a devotee (or anyone hitting
    # the API directly) cannot bypass this.
    # ------------------------------------------------------------------
    def validate(self, attrs):
        if self.instance is not None:
            return attrs  # only gate booking *creation*, not admin edits

        seva = attrs.get("seva")
        if seva is None:
            raise serializers.ValidationError({"seva": "Seva is required."})

        if not seva.is_active:
            raise serializers.ValidationError({"seva": "This Seva is not available for booking."})

        if not seva.has_valid_schedule:
            raise serializers.ValidationError(
                {"seva": "This Seva does not have a start/end date & time configured yet."}
            )

        now = timezone.now()
        if now < seva.start_datetime:
            raise serializers.ValidationError(
                {"seva": f"Booking is not open yet. This Seva starts at {seva.start_datetime.isoformat()}."}
            )
        if now > seva.end_datetime:
            raise serializers.ValidationError(
                {"seva": "This Seva's booking window has already ended."}
            )
        return attrs


class MealBookingSerializer(serializers.ModelSerializer):
    devotee_name = serializers.CharField(source="devotee.full_name", read_only=True)
    qr_image = serializers.SerializerMethodField()

    class Meta:
        model = MealBooking
        fields = [
            "id", "booking_code", "devotee", "devotee_name",
            "meal_name", "meal_date", "meal_time", "amount", "status", "created_at",
            "encrypted_qr", "qr_generated_at", "qr_scanned_at", "is_used", "qr_image",
        ]
        read_only_fields = [
            "id", "booking_code", "created_at",
            "encrypted_qr", "qr_generated_at", "qr_scanned_at", "is_used", "qr_image",
        ]

    def get_qr_image(self, obj):
        if not obj.encrypted_qr:
            return None
        return render_qr_image(obj.encrypted_qr)


class ScanBookingQRRequestSerializer(serializers.Serializer):
    """Body for POST /api/scan-booking-qr/ — Flutter forwards the raw
    encrypted string only, same contract as crowd_status's ScanQRView."""
    encrypted_data = serializers.CharField()


class BillSerializer(serializers.ModelSerializer):
    devotee_name = serializers.CharField(source="devotee.full_name", read_only=True)
    devotee_code = serializers.CharField(source="devotee.devotee_code", read_only=True)
    devotee_mobile = serializers.CharField(source="devotee.mobile", read_only=True)
    seva_name = serializers.CharField(source="seva.name", read_only=True)
    volunteer_name = serializers.CharField(source="volunteer.full_name", read_only=True, default=None)
    volunteer_code = serializers.CharField(source="volunteer.volunteer_code", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)

    class Meta:
        model = Bill
        fields = [
            "id", "bill_number", "invoice_number",
            "devotee", "devotee_name", "devotee_code", "devotee_mobile",
            "seva", "seva_name", "amount",
            "volunteer", "volunteer_name", "volunteer_code",
            "created_by", "created_by_name",
            "payment_status", "razorpay_order_id", "razorpay_payment_id",
            "created_at", "paid_at",
        ]
        read_only_fields = [
            "id", "bill_number", "invoice_number", "created_by",
            "payment_status", "razorpay_order_id", "razorpay_payment_id",
            "created_at", "paid_at",
        ]


class GenerateBillSerializer(serializers.Serializer):
    devotee = serializers.PrimaryKeyRelatedField(queryset=Devotee.objects.all())
    seva = serializers.PrimaryKeyRelatedField(queryset=Seva.objects.all())
    volunteer = serializers.PrimaryKeyRelatedField(queryset=Volunteer.objects.all(), required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)