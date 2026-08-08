# payments/views.py
import logging
import uuid

import razorpay
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import SevaPayment
from .serializers import CreateOrderSerializer, VerifyPaymentSerializer

logger = logging.getLogger(__name__)


def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def create_razorpay_order(request):
    serializer = CreateOrderSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Invalid request", "details": serializer.errors},
                         status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    amount = data["amount"]
    currency = data.get("currency", "INR")
    seva_name = data["seva_name"]
    receipt = f"seva_{uuid.uuid4().hex[:12]}"

    client = get_razorpay_client()
    try:
        order = client.order.create({
            "amount": amount,
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1,
            "notes": {"seva_name": seva_name},
        })
    except razorpay.errors.BadRequestError as exc:
        logger.exception("Razorpay order creation rejected")
        return Response({"error": "Razorpay rejected the order request", "details": str(exc)},
                         status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("Razorpay order creation failed")
        return Response({"error": "Could not create Razorpay order", "details": str(exc)},
                         status=status.HTTP_502_BAD_GATEWAY)

    SevaPayment.objects.create(
        seva_name=seva_name,
        amount=amount,
        currency=currency,
        razorpay_order_id=order["id"],
        receipt=receipt,
        payment_status=SevaPayment.Status.CREATED,
    )

    return Response({
        "id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key": settings.RAZORPAY_KEY_ID,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_razorpay_payment(request):
    serializer = VerifyPaymentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"verified": False, "message": "Invalid request", "details": serializer.errors},
                         status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    order_id = data["razorpay_order_id"]
    payment_id = data["razorpay_payment_id"]
    signature = data["razorpay_signature"]
    seva_name = data["seva_name"]
    amount = data["amount"]

    try:
        payment = SevaPayment.objects.get(razorpay_order_id=order_id)
    except SevaPayment.DoesNotExist:
        return Response({"verified": False, "message": "Order not found. Create an order first."},
                         status=status.HTTP_404_NOT_FOUND)

    # Idempotent: repeated verify calls for an already-paid order just succeed again.
    if payment.payment_status == SevaPayment.Status.PAID and payment.razorpay_payment_id == payment_id:
        return Response({
            "verified": True,
            "message": "Payment verified successfully",
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
        })

    # Trust the amount captured at order-creation time, not whatever the client resends.
    if payment.amount != amount:
        logger.warning("Amount mismatch on verify for %s: order=%s submitted=%s",
                        order_id, payment.amount, amount)
        return Response({"verified": False, "message": "Amount does not match the original order"},
                         status=status.HTTP_400_BAD_REQUEST)

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

    payment.razorpay_payment_id = payment_id
    payment.razorpay_signature = signature

    if not verified:
        payment.payment_status = SevaPayment.Status.FAILED
        payment.save(update_fields=["razorpay_payment_id", "razorpay_signature", "payment_status", "updated_at"])
        return Response({"verified": False, "message": "Invalid payment signature"},
                         status=status.HTTP_400_BAD_REQUEST)

    payment.payment_status = SevaPayment.Status.PAID
    payment.seva_name = seva_name
    payment.save()

    return Response({
        "verified": True,
        "message": "Payment verified successfully",
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
    })