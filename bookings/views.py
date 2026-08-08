import logging

import razorpay
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from crowd_status.permissions import IsVolunteerUser
from crowd_status.utils import QRDecryptionError, QRExpiredError, QRInvalidError, decrypt_payload

from .models import Bill, Booking, MealBooking, Seva
from .serializers import (
    BillSerializer, BookingSerializer, GenerateBillSerializer,
    MealBookingSerializer, ScanBookingQRRequestSerializer, SevaSerializer,
)

logger = logging.getLogger(__name__)


def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def _user_type(user):
    return getattr(user, "user_type", None)


class SevaViewSet(viewsets.ModelViewSet):
    queryset = Seva.objects.all()
    serializer_class = SevaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "is_active", "is_popular"]
    search_fields = ["name", "category", "priest"]
    ordering_fields = ["price", "name"]


class BookingViewSet(viewsets.ModelViewSet):
    """Devotees only ever see their own bookings (and therefore only their
    own Booking QR, per spec). Volunteers only see bookings they're
    attributed to — either created directly here (created_by) or via a bill
    they generated at the counter (bill.created_by), same scoping rule as
    BillViewSet below. Admins see every booking."""

    queryset = Booking.objects.select_related("devotee", "seva").all()
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "channel", "date", "seva"]
    search_fields = ["booking_code", "devotee__full_name", "seva__name"]
    ordering_fields = ["created_at", "date", "amount"]

    def get_queryset(self):
        qs = super().get_queryset()
        user_type = _user_type(self.request.user)
        if user_type == "devotee":
            return qs.filter(devotee__user=self.request.user)
        if user_type == "volunteer":
            return qs.filter(
                Q(created_by=self.request.user) | Q(bill__created_by=self.request.user)
            )
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(created_by=user if user.is_authenticated else None)


class MealBookingViewSet(viewsets.ModelViewSet):
    """Same visibility rule as BookingViewSet, for Meal Bookings."""

    queryset = MealBooking.objects.select_related("devotee").all()
    serializer_class = MealBookingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "meal_date"]
    search_fields = ["booking_code", "devotee__full_name", "meal_name"]
    ordering_fields = ["created_at", "meal_date", "amount"]

    def get_queryset(self):
        qs = super().get_queryset()
        if _user_type(self.request.user) == "devotee":
            return qs.filter(devotee__user=self.request.user)
        return qs


class ScanBookingQRView(APIView):
    """POST /api/scan-booking-qr/  { "encrypted_data": "gAAAAAB...." }

    Volunteer-only, mirrors crowd_status.ScanQRView's contract exactly:
    Flutter only forwards the raw string, backend decrypts and routes on
    qr_type ("seva" vs "meal"). Completely separate from the Attendance/
    Entry/Meal QR system — this is for booking-specific QR only.
    """
    permission_classes = [IsVolunteerUser]

    def post(self, request):
        serializer = ScanBookingQRRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        encrypted_data = serializer.validated_data["encrypted_data"]

        try:
            payload = decrypt_payload(encrypted_data)
        except QRExpiredError:
            return Response({"status": "failed", "message": "QR already used."}
                             if False else {"status": "failed", "message": "QR Expired"},
                             status=status.HTTP_400_BAD_REQUEST)
        except QRInvalidError:
            return Response({"status": "failed", "message": "Invalid QR"}, status=status.HTTP_400_BAD_REQUEST)
        except QRDecryptionError:
            return Response({"status": "failed", "message": "QR Verification Failed"}, status=status.HTTP_400_BAD_REQUEST)

        qr_type = payload.get("qr_type")
        if qr_type == "seva":
            return self._handle_seva(payload, request)
        if qr_type == "meal":
            return self._handle_meal(payload, request)
        return Response({"status": "failed", "message": "Unrecognized QR type"}, status=status.HTTP_400_BAD_REQUEST)

    def _handle_seva(self, payload, request):
        try:
            booking = Booking.objects.select_related("devotee", "seva").get(pk=payload.get("booking_id"))
        except Booking.DoesNotExist:
            return Response({"status": "failed", "message": "Booking Not Found"}, status=status.HTTP_404_NOT_FOUND)

        if booking.is_used:
            return Response({"status": "failed", "message": "QR already used."}, status=status.HTTP_400_BAD_REQUEST)

        booking.is_used = True
        booking.qr_scanned_at = timezone.now()
        booking.used_by_volunteer = request.user
        booking.save(update_fields=["is_used", "qr_scanned_at", "used_by_volunteer"])

        return Response({
            "status": "success",
            "type": "SEVA",
            "booking_reference": booking.booking_code,
            "devotee_name": booking.devotee.full_name,
            "seva_name": booking.seva.name,
            "date": str(booking.date),
            "time": booking.slot,
        })

    def _handle_meal(self, payload, request):
        try:
            meal_booking = MealBooking.objects.select_related("devotee").get(pk=payload.get("booking_id"))
        except MealBooking.DoesNotExist:
            return Response({"status": "failed", "message": "Booking Not Found"}, status=status.HTTP_404_NOT_FOUND)

        if meal_booking.is_used:
            return Response({"status": "failed", "message": "QR already used."}, status=status.HTTP_400_BAD_REQUEST)

        meal_booking.is_used = True
        meal_booking.qr_scanned_at = timezone.now()
        meal_booking.used_by_volunteer = request.user
        meal_booking.save(update_fields=["is_used", "qr_scanned_at", "used_by_volunteer"])

        return Response({
            "status": "success",
            "type": "MEAL",
            "booking_reference": meal_booking.booking_code,
            "devotee_name": meal_booking.devotee.full_name,
            "meal_name": meal_booking.meal_name,
            "date": str(meal_booking.meal_date),
            "time": meal_booking.meal_time,
        })


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.select_related("devotee", "seva", "volunteer", "created_by").all()
    serializer_class = BillSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["payment_status", "seva", "devotee", "volunteer"]
    search_fields = ["bill_number", "invoice_number", "devotee__full_name", "seva__name"]
    ordering_fields = ["created_at", "amount"]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        user_type = _user_type(user)
        if user_type == "volunteer":
            return qs.filter(created_by=user)
        if user_type == "devotee":
            return qs.filter(devotee__user=user)
        return qs

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        serializer = GenerateBillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        seva = data["seva"]
        amount = data.get("amount") or seva.price

        bill = Bill.objects.create(
            devotee=data["devotee"],
            seva=seva,
            amount=amount,
            volunteer=data.get("volunteer"),
            created_by=request.user if request.user.is_authenticated else None,
        )

        client = get_razorpay_client()
        try:
            order = client.order.create({
                "amount": int(amount * 100),
                "currency": "INR",
                "receipt": bill.bill_number,
                "payment_capture": 1,
                "notes": {"bill_number": bill.bill_number, "seva_name": seva.name},
            })
        except Exception as exc:
            logger.exception("Razorpay order creation failed for bill %s", bill.bill_number)
            bill.delete()
            return Response(
                {"error": "Could not create Razorpay order", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        bill.razorpay_order_id = order["id"]
        bill.save(update_fields=["razorpay_order_id"])

        return Response(
            {
                "bill": BillSerializer(bill).data,
                "razorpay": {
                    "order_id": order["id"],
                    "amount": order["amount"],
                    "currency": order["currency"],
                    "key": settings.RAZORPAY_KEY_ID,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        bill = self.get_object()
        payment_id = request.data.get("razorpay_payment_id")
        order_id = request.data.get("razorpay_order_id")
        signature = request.data.get("razorpay_signature")

        if not (payment_id and order_id and signature):
            return Response(
                {"verified": False, "message": "Missing Razorpay fields"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order_id != bill.razorpay_order_id:
            return Response(
                {"verified": False, "message": "Order does not match this bill"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if bill.payment_status == Bill.PaymentStatus.PAID:
            return Response({"verified": True, "bill": BillSerializer(bill).data})

        client = get_razorpay_client()
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            })
            verified = True
        except razorpay.errors.SignatureVerificationError:
            verified = False

        bill.razorpay_payment_id = payment_id
        bill.razorpay_signature = signature

        if not verified:
            bill.payment_status = Bill.PaymentStatus.FAILED
            bill.save(update_fields=["razorpay_payment_id", "razorpay_signature", "payment_status"])
            return Response(
                {"verified": False, "message": "Invalid payment signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bill.payment_status = Bill.PaymentStatus.PAID
        bill.paid_at = timezone.now()
        bill.save(update_fields=["razorpay_payment_id", "razorpay_signature", "payment_status", "paid_at"])

        if not hasattr(bill, "booking"):
            Booking.objects.create(
                devotee=bill.devotee,
                seva=bill.seva,
                date=timezone.localdate(),
                slot="Walk-in",
                amount=bill.amount,
                channel=Booking.Channel.COUNTER,
                status=Booking.Status.CONFIRMED,
                payment_id=payment_id,
                bill=bill,
                created_by=bill.created_by,
            )

        return Response({"verified": True, "bill": BillSerializer(bill).data})