from datetime import datetime

from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from bookings.models import Booking, Seva
from devotees.models import Devotee
from donations.models import Donation
from events.models import Event, Visitor
from inventory.models import InventoryItem
from volunteers.models import Volunteer

from .models import Alert, LiveDarshan, LiveFestivalInfo
from .permissions import IsAdminOrReadOnly, IsAdminUserType
from .serializers import (
    AlertSerializer,
    LiveDarshanSerializer,
    LiveDarshanStatusSerializer,
    LiveFestivalInfoSerializer,
)


def _active_seva_festival_entries():
    """Build virtual Live-Festival-Info entries from Sevas that carry an
    optional seva_date/start_time/end_time. Reuses the SAME API shape as
    LiveFestivalInfo — no second Live Festival system, no extra admin form.
    """
    now_local = timezone.localtime(timezone.now())
    today = now_local.date()
    current_time = now_local.time()

    entries = []
    qs = Seva.objects.filter(is_active=True, start_date__lte=today, end_date__gte=today)
    for seva in qs:
        # CASE 4: no start/end at all -> never auto-shows as Live here.
        if seva.start_time is None and seva.end_time is None:
            continue

        start_ok = seva.start_time is None or current_time >= seva.start_time
        end_ok = seva.end_time is None or current_time <= seva.end_time
        if not (start_ok and end_ok):
            continue

        start_dt = (
            timezone.make_aware(datetime.combine(today, seva.start_time))
            if seva.start_time else None
        )
        end_dt = (
            timezone.make_aware(datetime.combine(today, seva.end_time))
            if seva.end_time else None
        )
        entries.append({
            "id": f"seva-{seva.id}",
            "title": seva.name,
            "start_time": start_dt.isoformat() if start_dt else None,
            "end_time": end_dt.isoformat() if end_dt else None,
            "description": seva.description,
            "is_active": True,
            "created_at": None,
            "updated_at": None,
            "source": "seva",
        })
    return entries


class LiveDarshanViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for "Live Darshan Management" (Add/Edit/Delete/
    Activate). POST/PUT/PATCH/DELETE — AND GET on this ViewSet — all
    return 403 for any non-admin user via IsAdminUserType.

    Volunteers/devotees never call this; they use the public, read-only
    `live_darshan_status` view below instead, which has its own
    permission (IsAuthenticated) and its own trimmed response shape.
    """

    queryset = LiveDarshan.objects.all()
    serializer_class = LiveDarshanSerializer
    permission_classes = [IsAdminUserType]

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        self._deactivate_others(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._deactivate_others(instance)

    def _deactivate_others(self, instance):
        """Only one Live Darshan should be active at a time — when this
        one is turned on, switch every other one off."""
        if instance.is_live:
            LiveDarshan.objects.filter(is_live=True).exclude(pk=instance.pk).update(is_live=False)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def live_darshan_status(request):
    """GET /api/dashboard/live-darshan/ — polled by Admin/Volunteer/
    Devotee dashboards (React) and the Volunteer app (Flutter) to decide
    whether to show the "LIVE" banner. Any authenticated user can call
    this; only admins can write, via LiveDarshanViewSet's IsAdminUserType.

    DB-driven (NOT settings.GANPATI_LIVE_URL) — picks the most recent
    LiveDarshan row whose effective_is_live is True. If none matches,
    returns {"is_live": false, "title": null, "live_url": null}.
    """
    current = None
    for candidate in LiveDarshan.objects.filter(is_live=True).order_by("-start_datetime", "-created_at"):
        if candidate.effective_is_live:
            current = candidate
            break

    if not current:
        return Response({"is_live": False, "title": None, "live_url": None})

    return Response(LiveDarshanStatusSerializer(current, context={"request": request}).data)


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer


class LiveFestivalInfoViewSet(viewsets.ModelViewSet):
    """CRUD API for the Command Dashboard's "Live Festival Info" widget.

    GET (list/retrieve): any authenticated user (admin, volunteer, devotee).
    POST/PUT/PATCH/DELETE: admins only — see IsAdminOrReadOnly.
    """

    queryset = LiveFestivalInfo.objects.all()
    serializer_class = LiveFestivalInfoSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active_only") == "true":
            qs = qs.filter(is_active=True)
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        data = list(self.get_serializer(qs, many=True).data)
        data.extend(_active_seva_festival_entries())
        return Response(data)


def _manual_counter_total_inside() -> int:
    """Sum of everyone currently inside via the Manual Counter (walk-ins
    without a QR scan), across all areas. Computed per-area (increments
    minus decrements, floored at 0 — same rule ManualCounter.current_count_for_area
    already applies per area) and then summed, so one area's decrements
    can't cancel out another area's increments.

    Local import avoids a hard dependency between the crowd_status app and
    the dashboard app at module load time.
    """
    from crowd_status.models import ManualCounter

    areas = ManualCounter.objects.values_list("assigned_area", flat=True).distinct()
    return sum(ManualCounter.current_count_for_area(area) for area in areas)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """GET /api/dashboard/stats/ — headline KPIs for the command centre."""
    today = timezone.now().date()

    qr_visitors = Visitor.objects.filter(status=Visitor.Status.INSIDE).count()
    manual_visitors = _manual_counter_total_inside()
    live_visitors = qr_visitors + manual_visitors

    todays_bookings = Booking.objects.filter(date=today).count()
    todays_donations = Donation.objects.filter(created_at__date=today).aggregate(total=Sum("amount"))["total"] or 0
    volunteers_on_duty = Volunteer.objects.filter(status=Volunteer.Status.ADMIN_APPROVED).count()
    total_volunteers = Volunteer.objects.count()
    revenue_mtd = Donation.objects.filter(created_at__month=today.month, created_at__year=today.year).aggregate(
        total=Sum("amount")
    )["total"] or 0

    return Response(
        {
            "liveVisitors": {"value": live_visitors},
            "todaysBookings": {"value": todays_bookings},
            "todaysDonations": {"value": float(todays_donations)},
            "volunteersOnDuty": {"value": f"{volunteers_on_duty} / {total_volunteers}"},
            "revenueMTD": {"value": float(revenue_mtd)},
            "totalDevotees": {"value": Devotee.objects.count()},
            "totalEvents": {"value": Event.objects.count()},
            "inventoryAlerts": {
                "value": sum(1 for item in InventoryItem.objects.all() if item.status != InventoryItem.Status.OK)
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def visitor_flow(request):
    """GET /api/dashboard/visitor-flow/ — hourly visitor/booking counts for today."""
    from django.db.models.functions import ExtractHour

    today = timezone.now().date()
    visitors_by_hour = (
        Visitor.objects.filter(check_in__date=today)
        .annotate(hour=ExtractHour("check_in"))
        .values("hour")
        .order_by("hour")
    )
    bookings_by_hour = (
        Booking.objects.filter(date=today)
        .annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .order_by("hour")
    )

    visitor_counts = {row["hour"]: 0 for row in visitors_by_hour}
    for row in Visitor.objects.filter(check_in__date=today):
        visitor_counts[row.check_in.hour] = visitor_counts.get(row.check_in.hour, 0) + 1

    booking_counts = {}
    for b in Booking.objects.filter(date=today):
        h = b.created_at.hour
        booking_counts[h] = booking_counts.get(h, 0) + 1

    result = []
    for hour in range(0, 24, 2):
        result.append(
            {
                "hour": f"{hour:02d}:00",
                "visitors": visitor_counts.get(hour, 0),
                "bookings": booking_counts.get(hour, 0),
            }
        )
    return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def revenue_mix(request):
    """GET /api/dashboard/revenue-mix/ — revenue split by donation purpose (proxy for revenue sources)."""
    qs = Donation.objects.values("purpose").annotate(value=Sum("amount")).order_by("-value")
    return Response([{"name": row["purpose"], "value": float(row["value"] or 0)} for row in qs])