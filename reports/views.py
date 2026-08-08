from django.db.models import Sum, Count
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from bookings.models import Booking
from donations.models import Donation
from volunteers.models import Volunteer
from devotees.models import Devotee

from .models import SavedReport
from .serializers import SavedReportSerializer


class SavedReportViewSet(viewsets.ModelViewSet):
    queryset = SavedReport.objects.all()
    serializer_class = SavedReportSerializer

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary_report(request):
    """GET /api/reports/summary/ — cross-module totals for reporting dashboards."""
    return Response(
        {
            "total_devotees": Devotee.objects.count(),
            "total_volunteers": Volunteer.objects.filter(status=Volunteer.Status.ACTIVE).count(),
            "total_bookings": Booking.objects.count(),
            "total_donations": float(Donation.objects.aggregate(total=Sum("amount"))["total"] or 0),
            "bookings_by_status": list(Booking.objects.values("status").annotate(count=Count("id"))),
            "donations_by_purpose": list(
                Donation.objects.values("purpose").annotate(total=Sum("amount"))
            ),
        }
    )
