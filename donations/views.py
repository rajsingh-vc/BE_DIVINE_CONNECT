import logging
from datetime import timedelta

import razorpay
from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Donation
from .serializers import DonationSerializer, GenerateDonationSerializer

logger = logging.getLogger(__name__)


def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


# Colors line up with the tokens already used on the frontend's trend chart
# (hsl(35 90% 55%) etc) so the pie stays visually consistent with the rest
# of the dashboard.
PURPOSE_COLORS = {
    Donation.Purpose.GENERAL: "hsl(35 90% 55%)",       # amber
    Donation.Purpose.ANNADAAN: "hsl(160 60% 45%)",      # emerald
    Donation.Purpose.CONSTRUCTION: "hsl(200 70% 55%)",  # sky
    Donation.Purpose.EDUCATION: "hsl(14 70% 55%)",      # terracotta
}


class DonationViewSet(viewsets.ModelViewSet):
    """
    Donation API.

    - GET/POST/... on the base route: admin console CRUD (list, create,
      retrieve, update, delete) — requires auth, same as every other
      console resource. The admin "Recent Donations" list is just this
      route with `?ordering=-created_at` (the default) and pagination —
      there's no separate /recent/ endpoint.
    - POST /generate/ and POST /<id>/verify/: the public donation flow
      (amount + anonymous toggle + donor info + optional tax receipt ->
      Razorpay order -> verify payment). Open to unauthenticated donors,
      same pattern as the Sevas & Services "Generate Bill" flow.
    - GET /trend/, /stats/, /mix/: aggregated numbers for the admin
      dashboard's stat cards and charts.
    """

    queryset = Donation.objects.select_related("devotee").all()
    serializer_class = DonationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["purpose", "is_anonymous", "payment_status"]
    search_fields = ["donation_code", "donor_name", "devotee__full_name"]
    ordering_fields = ["created_at", "amount"]

    def get_permissions(self):
        if self.action in ("generate", "verify", "bill_summary"):
            return [AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=["get"], url_path="trend")
    def trend(self, request):
        """GET /api/donations/trend/ — monthly totals for the trend chart."""
        qs = (
            self.get_queryset()
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(amount=Sum("amount"))
            .order_by("month")
        )
        return Response(
            [{"month": row["month"].strftime("%b") if row["month"] else "", "amount": float(row["amount"] or 0)} for row in qs]
        )

    @action(detail=False, methods=["get"], url_path="mix")
    def mix(self, request):
        """GET /api/donations/mix/ — totals grouped by purpose, for the
        "Category mix" pie chart. Only paid donations count towards the mix."""
        qs = (
            self.get_queryset()
            .filter(payment_status=Donation.PaymentStatus.PAID)
            .values("purpose")
            .annotate(value=Sum("total_amount"))
            .order_by("-value")
        )
        labels = dict(Donation.Purpose.choices)
        return Response(
            [
                {
                    "name": labels.get(row["purpose"], row["purpose"]),
                    "value": float(row["value"] or 0),
                    "color": PURPOSE_COLORS.get(row["purpose"], "hsl(30 10% 55%)"),
                }
                for row in qs
            ]
        )

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """GET /api/donations/stats/ — figures behind the four stat cards
        at the top of the admin dashboard. Only paid donations count."""
        now = timezone.now()
        today = now.date()
        month_start = today.replace(day=1)
        days_elapsed = (today - month_start).days + 1

        # Same number of days last month, so month-to-date comparisons are
        # apples-to-apples rather than comparing a partial month to a full one.
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        prev_period_end = min(prev_month_start + timedelta(days=days_elapsed - 1), prev_month_end)

        paid = self.get_queryset().filter(payment_status=Donation.PaymentStatus.PAID)

        received_today = paid.filter(paid_at__date=today).aggregate(total=Sum("total_amount"))["total"] or 0

        mtd_total = paid.filter(paid_at__date__gte=month_start, paid_at__date__lte=today).aggregate(
            total=Sum("total_amount")
        )["total"] or 0

        prev_mtd_total = paid.filter(
            paid_at__date__gte=prev_month_start, paid_at__date__lte=prev_period_end
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        mtd_change_percent = None
        if prev_mtd_total:
            mtd_change_percent = round((float(mtd_total) - float(prev_mtd_total)) / float(prev_mtd_total) * 100, 1)

        # "Donors this month" — distinct devotees with a paid donation this
        # month, plus one for each paid donation with no linked devotee
        # (walk-in / anonymous donors aren't deduplicated).
        this_month_paid = paid.filter(paid_at__date__gte=month_start, paid_at__date__lte=today)
        named_donor_count = this_month_paid.exclude(devotee__isnull=True).values("devotee_id").distinct().count()
        unlinked_donation_count = this_month_paid.filter(devotee__isnull=True).count()
        donors_this_month = named_donor_count + unlinked_donation_count

        # "Recurring" — devotees with more than one paid donation, ever.
        recurring_donors = (
            paid.exclude(devotee__isnull=True)
            .values("devotee_id")
            .annotate(donation_count=Count("id"))
            .filter(donation_count__gt=1)
            .count()
        )

        return Response(
            {
                "received_today": float(received_today),
                "mtd_total": float(mtd_total),
                "mtd_change_percent": mtd_change_percent,
                "donors_this_month": donors_this_month,
                "recurring_donors": recurring_donors,
            }
        )

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """Step 1 — donor submits the donation form:
            amount, is_anonymous, donor information, optional 80G receipt
        Creates a pending Donation (fee + total pre-computed) and a matching
        Razorpay order sized to the donation + platform fee, and returns the
        bill summary for the donor to confirm before paying.
        """
        serializer = GenerateDonationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        is_anonymous = data["is_anonymous"]

        donation = Donation.objects.create(
            devotee=data.get("devotee"),
            amount=data["amount"],
            is_anonymous=is_anonymous,
            donor_name="" if is_anonymous else data.get("donor_name", ""),
            donor_email=data.get("donor_email", ""),
            donor_mobile=data.get("donor_mobile", ""),
            donor_address=data.get("donor_address", ""),
            want_80g_receipt=data.get("want_80g_receipt", False),
            donor_pan=data.get("donor_pan", ""),
            purpose=data.get("purpose", Donation.Purpose.GENERAL),
        )

        client = get_razorpay_client()
        try:
            order = client.order.create(
                {
                    "amount": int(donation.total_amount * 100),  # paise — donation + platform fee
                    "currency": "INR",
                    "receipt": donation.donation_code,
                    "payment_capture": 1,
                    "notes": {"donation_code": donation.donation_code, "purpose": donation.purpose},
                }
            )
        except Exception as exc:
            logger.exception("Razorpay order creation failed for donation %s", donation.donation_code)
            donation.delete()
            return Response(
                {"error": "Could not create Razorpay order", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        donation.razorpay_order_id = order["id"]
        donation.save(update_fields=["razorpay_order_id"])

        return Response(
            {
                "donation": DonationSerializer(donation).data,
                "bill_summary": donation.bill_summary,
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
        """Step 2 — verify the Razorpay signature returned by checkout.js and
        mark the donation Paid, issuing a receipt number when requested."""
        donation = self.get_object()
        payment_id = request.data.get("razorpay_payment_id")
        order_id = request.data.get("razorpay_order_id")
        signature = request.data.get("razorpay_signature")

        if not (payment_id and order_id and signature):
            return Response(
                {"verified": False, "message": "Missing Razorpay fields"}, status=status.HTTP_400_BAD_REQUEST
            )

        if order_id != donation.razorpay_order_id:
            return Response(
                {"verified": False, "message": "Order does not match this donation"}, status=status.HTTP_400_BAD_REQUEST
            )

        if donation.payment_status == Donation.PaymentStatus.PAID:
            return Response({"verified": True, "donation": DonationSerializer(donation).data})

        client = get_razorpay_client()
        try:
            client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                }
            )
            verified = True
        except razorpay.errors.SignatureVerificationError:
            verified = False

        donation.razorpay_payment_id = payment_id
        donation.razorpay_signature = signature

        if not verified:
            donation.payment_status = Donation.PaymentStatus.FAILED
            donation.save(update_fields=["razorpay_payment_id", "razorpay_signature", "payment_status"])
            return Response(
                {"verified": False, "message": "Invalid payment signature"}, status=status.HTTP_400_BAD_REQUEST
            )

        donation.payment_status = Donation.PaymentStatus.PAID
        donation.payment_reference = payment_id
        donation.paid_at = timezone.now()
        donation.save(
            update_fields=[
                "payment_status", "payment_reference", "paid_at", "razorpay_payment_id", "razorpay_signature",
            ]
        )

        # Keep the linked devotee's running donation total in sync, if any.
        if donation.devotee_id:
            devotee = donation.devotee
            devotee.total_donated = (devotee.total_donated or 0) + donation.amount
            devotee.save(update_fields=["total_donated"])

        return Response(
            {"verified": True, "donation": DonationSerializer(donation).data, "bill_summary": donation.bill_summary}
        )

    @action(detail=True, methods=["get"], url_path="bill-summary")
    def bill_summary(self, request, pk=None):
        """GET /api/donations/<id>/bill-summary/ — donor, donation amount,
        platform fee and total, with the donor name withheld when the
        donation was made anonymously."""
        donation = self.get_object()
        return Response(donation.bill_summary)