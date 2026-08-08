from django.contrib.auth import get_user_model
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from volunteers.models import Notification
from volunteers.notifications import notify

from .models import SOSAlert
from .permissions import SOSAlertPermission, _is_admin
from .serializers import SOSAlertSerializer


class SOSAlertViewSet(viewsets.ModelViewSet):
    """
    /api/sos/alerts/

    GET     list / retrieve  -> admin, volunteer, devotee (anyone logged in)
    POST    create           -> volunteer, admin   (the panic-button tap)
    PUT/PATCH                -> admin (any alert), volunteer (own alerts only)
    DELETE                   -> admin (any alert), volunteer (own alerts only)

    Side effects:
    - On create: every admin gets an immediate bell notification
      ("Emergency SOS").
    - On update: if an admin writes/changes `resolution_notes` (the Admin
      Response field), the volunteer who raised the alert gets a bell
      notification and `response_status` flips from "awaiting_response" to
      "responded".
    """

    queryset = SOSAlert.objects.select_related("raised_by", "resolved_by").all()
    serializer_class = SOSAlertSerializer
    permission_classes = [IsAuthenticated, SOSAlertPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["alert_type", "status"]
    search_fields = ["sos_code", "description", "location"]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        alert = serializer.save(raised_by=self.request.user)
        self._notify_admins_new_sos(alert)

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user

        if not _is_admin(user):
            # A volunteer editing their own alert can only touch the core
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
        elif new_status in (SOSAlert.Status.RESOLVED, SOSAlert.Status.CLOSED):
            # Keep the original resolver if it's already set, otherwise
            # credit whoever just made the change.
            resolved_by = instance.resolved_by or user

        alert = serializer.save(resolved_by=resolved_by, responded_at=responded_at)

        if is_new_response:
            self._notify_raiser_of_response(alert)

    def _notify_admins_new_sos(self, alert):
        User = get_user_model()
        admins = User.objects.filter(is_staff=True) | User.objects.filter(user_type="admin")
        where = f" near {alert.location}" if alert.location else ""
        for admin in admins.distinct():
            if admin.id == alert.raised_by_id:
                continue
            notify(
                admin,
                "Emergency SOS",
                f"{alert.sos_code} — {alert.get_alert_type_display()} raised by "
                f"{alert.raised_by.full_name if alert.raised_by else 'a volunteer'}{where}.",
                Notification.Type.SOS_ALERT,
                related_sos=alert,
            )

    def _notify_raiser_of_response(self, alert):
        if not alert.raised_by or alert.raised_by_id == self.request.user.id:
            return
        notify(
            alert.raised_by,
            "Your Emergency SOS got a response",
            f"Admin responded to {alert.sos_code} — {alert.get_alert_type_display()}.",
            Notification.Type.SOS_RESPONSE,
            related_sos=alert,
        )