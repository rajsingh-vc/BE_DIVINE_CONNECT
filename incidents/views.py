from django.contrib.auth import get_user_model
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from volunteers.models import Notification
from volunteers.notifications import notify

from .models import IncidentReport
from .permissions import IncidentReportPermission, _is_admin
from .serializers import IncidentReportSerializer


class IncidentReportViewSet(viewsets.ModelViewSet):
    """
    /api/incidents/incidents/

    GET     list / retrieve  -> admin, volunteer, devotee (anyone logged in)
    POST    create           -> volunteer, admin
    PUT/PATCH               -> admin (any report), volunteer (own reports only)
    DELETE                  -> admin (any report), volunteer (own reports only)

    Side effects:
    - On create: every admin gets a bell notification ("New Incident Reported").
    - On update: if an admin writes/changes `resolution_notes` (the Admin
      Response field), the reporting volunteer gets a bell notification and
      the incident's `response_status` flips from "awaiting_response" to
      "responded".
    """

    queryset = IncidentReport.objects.select_related("reported_by", "resolved_by").all()
    serializer_class = IncidentReportSerializer
    permission_classes = [IsAuthenticated, IncidentReportPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "severity", "status"]
    search_fields = ["title", "description", "incident_code", "location"]
    ordering_fields = ["created_at", "severity", "status"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        incident = serializer.save(reported_by=self.request.user)
        self._notify_admins_new_incident(incident)

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user

        if not _is_admin(user):
            # A volunteer editing their own report can only touch the core
            # fields — status and the admin response are admin-only, no
            # matter what the client sends.
            serializer.validated_data.pop("status", None)
            serializer.validated_data.pop("resolution_notes", None)
            serializer.save()
            return

        new_status = serializer.validated_data.get("status", instance.status)
        new_notes = serializer.validated_data.get("resolution_notes", instance.resolution_notes)
        is_new_response = bool(new_notes.strip()) and new_notes != instance.resolution_notes

        resolved_by = instance.resolved_by
        responded_at = instance.responded_at
        if is_new_response:
            resolved_by = user
            responded_at = timezone.now()
        elif new_status in (IncidentReport.Status.RESOLVED, IncidentReport.Status.CLOSED):
            # Keep the original resolver if it's already set, otherwise
            # credit whoever just made the change.
            resolved_by = instance.resolved_by or user

        incident = serializer.save(resolved_by=resolved_by, responded_at=responded_at)

        if is_new_response:
            self._notify_reporter_of_response(incident)

    def _notify_admins_new_incident(self, incident):
        User = get_user_model()
        admins = User.objects.filter(is_staff=True) | User.objects.filter(user_type="admin")
        for admin in admins.distinct():
            if admin.id == incident.reported_by_id:
                continue
            notify(
                admin,
                "New Incident Reported",
                f"{incident.incident_code} — {incident.title} ({incident.get_severity_display()} · {incident.get_category_display()})",
                Notification.Type.INCIDENT_REPORTED,
                related_incident=incident,
            )

    def _notify_reporter_of_response(self, incident):
        if not incident.reported_by or incident.reported_by_id == self.request.user.id:
            return
        notify(
            incident.reported_by,
            "Your incident report got a response",
            f"Admin responded to {incident.incident_code} — {incident.title}.",
            Notification.Type.INCIDENT_RESPONSE,
            related_incident=incident,
        )