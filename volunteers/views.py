import base64

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Volunteer, Verification, VolunteerApproval, Notification, AuditLog, VolunteerIdSequence, Duty
from .permissions import IsAdminOrReadOnly
from .serializers import (
    VolunteerListSerializer, VolunteerDetailSerializer, VolunteerRegisterSerializer,
    VolunteerApplySerializer, ReferenceActionSerializer, AdminActionSerializer,
    NotificationSerializer, AuditLogSerializer,
    DutySerializer, DutyAssignSerializer, DutyHelpSerializer,
    DutySwapResponseSerializer, SwapCandidateSerializer,
)
from .notifications import (
    notify, notify_reference_required, notify_admins_new_application,
    notify_duty_assigned, notify_duty_accepted, notify_duty_completed, notify_duty_help_requested,
    notify_duty_swap_requested, notify_duty_swap_responded,
    notify_volunteers_meal_session,
)
from .realtime import push_status_update

User = get_user_model()


from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import MealSession, MealCheckIn, generate_code
from .serializers import MealSessionSerializer, MealCheckInSerializer
from .permissions import IsAdminOrReadOnly  # reuse whatever admin-write/read-all permission you already have


class MealSessionViewSet(viewsets.ModelViewSet):
    """Admin creates/edits meal windows (gate + start/end time). Everyone
    authenticated can list (needed so the volunteer app can find the active
    session for scanning). Creating a session notifies every approved
    volunteer that meal check-in is open."""
    queryset = MealSession.objects.all().order_by("-start_time")
    serializer_class = MealSessionSerializer
    permission_classes = [IsAdminOrReadOnly]

    def perform_create(self, serializer):
        session = serializer.save(created_by=self.request.user)
        notify_volunteers_meal_session(session)

    @action(detail=False, methods=["get"])
    def active(self, request):
        now = timezone.now()
        sessions = self.get_queryset().filter(is_active=True, start_time__lte=now, end_time__gte=now)
        return Response(MealSessionSerializer(sessions, many=True).data)

    @action(detail=True, methods=["get"], permission_classes=[IsAdminUser])
    def token(self, request, pk=None):
        """Kiosk/gate-display endpoint — polls this every ~10-15s to refresh the QR image.
        Pure crypto, no DB write, so this is safe to hit frequently."""
        session = self.get_object()
        if not session.is_open():
            return Response({"detail": "This meal session is not currently open."}, status=400)
        return Response({"token": session.current_token(), "ttl_seconds": 15})

    @action(detail=True, methods=["get"], url_path="my-qr", permission_classes=[IsAuthenticated])
    def my_qr(self, request, pk=None):
        """Volunteer-facing: polls this every ~10-12s to render/refresh their own
        personal QR on screen. Pure crypto, no DB write — same shape as `token`
        above, but the payload identifies the requesting volunteer, not the gate."""
        session = self.get_object()
        if not session.is_open():
            return Response({"detail": "This meal session is not currently open."}, status=400)

        vol = getattr(request.user, "volunteer_profile_v2", None)
        if not vol or not (vol.is_volunteer and vol.status == Volunteer.Status.ADMIN_APPROVED):
            return Response({"detail": "No approved volunteer profile found for this account."}, status=403)

        token = session.personal_token(vol.id)
        return Response({"token": token, "ttl_seconds": 15, "volunteer_code": vol.volunteer_code})

    @action(detail=True, methods=["get"], permission_classes=[IsAdminUser])
    def checkins(self, request, pk=None):
        session = self.get_object()
        rows = session.checkins.select_related("volunteer").order_by("-check_in_time")
        return Response(MealCheckInSerializer(rows, many=True).data)


def _decode_meal_scan(token):
    """Shared token-decode/lookup used by both MealScanView.post (writes) and
    MealScanView.get (read-only peek). Decodes a volunteer's personal QR token
    and resolves which volunteer it belongs to. Returns (session, volunteer,
    error_response) — exactly one of (session, volunteer) or error_response
    will be non-None."""
    if not token:
        return None, None, Response({"detail": "Missing token."}, status=400)

    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        session_id = int(raw.split(":")[0])
    except Exception:
        return None, None, Response({"detail": "Invalid QR code."}, status=400)

    try:
        session = MealSession.objects.get(id=session_id)
    except MealSession.DoesNotExist:
        return None, None, Response({"detail": "Invalid QR code."}, status=400)

    volunteer_id = session.verify_personal_token(token)
    if volunteer_id is None:
        return None, None, Response(
            {"detail": "This QR code has expired. Ask the volunteer to refresh it and rescan."}, status=400
        )

    if not session.is_open():
        return None, None, Response({"detail": "This meal session is not currently open."}, status=400)

    try:
        volunteer = Volunteer.objects.select_related("user").get(id=volunteer_id)
    except Volunteer.DoesNotExist:
        return None, None, Response({"detail": "Volunteer not found."}, status=400)

    if not volunteer.user:
        return None, None, Response({"detail": "This volunteer has no linked login account."}, status=400)

    if not (volunteer.is_volunteer and volunteer.status == Volunteer.Status.ADMIN_APPROVED):
        return None, None, Response(
            {"detail": f"{volunteer.name} is not currently an approved volunteer."}, status=400
        )

    return session, volunteer, None


class MealScanView(APIView):
    """Kiosk-facing: scans a volunteer's personal QR to check them in, scans
    again to check them out. Identity comes from the QR's signed payload —
    never from request.user, since the account logged in on this device is
    the kiosk operator's, not the volunteer's."""
    permission_classes = [IsAdminUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "meal_scan"

    def post(self, request):
        token = request.data.get("token", "")
        session, volunteer, error = _decode_meal_scan(token)
        if error:
            return error

        ip = request.META.get("REMOTE_ADDR")

        with transaction.atomic():
            record, created = MealCheckIn.objects.select_for_update().get_or_create(
                session=session,
                volunteer=volunteer.user,
                defaults={
                    "assigned_role": _snapshot_role(volunteer.user),
                    "shift_timing": _snapshot_shift(volunteer.user),
                    "status": "checked_in",
                    "check_in_time": timezone.now(),
                    "device_ip": ip,
                },
            )
            if not created:
                if record.status == "checked_in":
                    record.status = "checked_out"
                    record.check_out_time = timezone.now()
                else:
                    record.status = "checked_in"
                    record.check_in_time = timezone.now()
                    record.check_out_time = None
                record.scan_count += 1
                record.device_ip = ip
                record.save(update_fields=["status", "check_in_time", "check_out_time", "scan_count", "device_ip", "updated_at"])

        return Response(MealCheckInSerializer(record).data, status=200)

    def get(self, request):
        """Read-only peek: given a scanned token, report what the *next* scan
        would do (check in vs check out) without writing anything to the DB.
        Lets the kiosk UI label its confirm state correctly ("Check In" vs
        "Check Out") before committing. Same token validation as post(), just
        no MealCheckIn is created/updated here."""
        token = request.query_params.get("token", "")
        session, volunteer, error = _decode_meal_scan(token)
        if error:
            return error

        existing = MealCheckIn.objects.filter(session=session, volunteer=volunteer.user).first()
        if not existing or existing.status == "checked_out":
            next_action = "checked_in"
        else:
            next_action = "checked_out"

        return Response({
            "session_id": session.id,
            "location": session.location,
            "volunteer_name": volunteer.name,
            "volunteer_code": volunteer.volunteer_code,
            "next_action": next_action,  # "checked_in" | "checked_out"
        })


class MealSelfScanView(APIView):
    """Volunteer-facing self-scan: the volunteer scans the *gate* QR that the
    admin's kiosk device displays (the plain session-level token from the
    `token` action) with their own phone camera. Identity comes from
    request.user this time — the token only proves which session/time-window
    this is, not who's scanning it — so this checks the *logged-in
    volunteer* in/out, unlike MealScanView which checks in whoever the QR
    payload identifies."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "meal_scan"

    def post(self, request):
        token = request.data.get("token", "")
        if not token:
            return Response({"detail": "Missing token."}, status=400)

        try:
            raw = base64.urlsafe_b64decode(token.encode()).decode()
            session_id = int(raw.split(":")[0])
        except Exception:
            return Response({"detail": "Invalid QR code."}, status=400)

        try:
            session = MealSession.objects.get(id=session_id)
        except MealSession.DoesNotExist:
            return Response({"detail": "Invalid QR code."}, status=400)

        if not session.verify_token(token):
            return Response(
                {"detail": "This QR code has expired. Ask the gate to refresh it and rescan."}, status=400
            )

        if not session.is_open():
            return Response({"detail": "This meal session is not currently open."}, status=400)

        vol = getattr(request.user, "volunteer_profile_v2", None)
        if not vol or not (vol.is_volunteer and vol.status == Volunteer.Status.ADMIN_APPROVED):
            return Response({"detail": "No approved volunteer profile found for this account."}, status=403)

        ip = request.META.get("REMOTE_ADDR")

        with transaction.atomic():
            record, created = MealCheckIn.objects.select_for_update().get_or_create(
                session=session,
                volunteer=request.user,
                defaults={
                    "assigned_role": _snapshot_role(request.user),
                    "shift_timing": _snapshot_shift(request.user),
                    "status": "checked_in",
                    "check_in_time": timezone.now(),
                    "device_ip": ip,
                },
            )
            if not created:
                if record.status == "checked_in":
                    record.status = "checked_out"
                    record.check_out_time = timezone.now()
                else:
                    record.status = "checked_in"
                    record.check_in_time = timezone.now()
                    record.check_out_time = None
                record.scan_count += 1
                record.device_ip = ip
                record.save(update_fields=["status", "check_in_time", "check_out_time", "scan_count", "device_ip", "updated_at"])

        return Response(MealCheckInSerializer(record).data, status=200)


def _snapshot_role(user):
    vol = getattr(user, "volunteer_profile_v2", None)
    return getattr(vol, "assigned_role", "") if vol else ""


def _snapshot_shift(user):
    # Best-effort: pull today's duty time as the "shift".
    vol = getattr(user, "volunteer_profile_v2", None)
    if not vol:
        return ""
    from .models import Duty
    today_duty = Duty.objects.filter(volunteer=vol, duty_date=timezone.localdate()).order_by("time").first()
    if today_duty and today_duty.time:
        return today_duty.time.strftime("%H:%M")
    return ""


class MealStatsView(APIView):
    """Admin analytics: how many times each volunteer scanned, broken down by zone/location."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = (
            MealCheckIn.objects.values("volunteer__full_name", "volunteer_id", "session__location")
            .annotate(scans=Count("id"))
            .order_by("volunteer__full_name")
        )
        by_volunteer = {}
        for r in rows:
            key = r["volunteer_id"]
            entry = by_volunteer.setdefault(key, {
                "volunteer_id": key,
                "volunteer_name": r["volunteer__full_name"],
                "total_scans": 0,
                "by_location": {},
            })
            entry["total_scans"] += r["scans"]
            entry["by_location"][r["session__location"]] = r["scans"]

        return Response(list(by_volunteer.values()))


class IsApprovedVolunteer(permissions.BasePermission):
    def has_permission(self, request, view):
        vol = getattr(request.user, "volunteer_profile_v2", None)
        return bool(vol and vol.can_register_volunteers)


class VolunteerViewSet(viewsets.ModelViewSet):
    queryset = Volunteer.objects.select_related("reference_volunteer", "approval", "verification")
    permission_classes = [IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VolunteerDetailSerializer
        return VolunteerListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        status_filter = self.request.query_params.get("status")
        is_volunteer_filter = self.request.query_params.get("is_volunteer")
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(phone__icontains=search) | qs.filter(email__icontains=search)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if is_volunteer_filter is not None:
            qs = qs.filter(is_volunteer=is_volunteer_filter.lower() in ("1", "true", "yes"))
        return qs.order_by(self.request.query_params.get("ordering", "-created_at"))

    @action(detail=False, methods=["post"], url_path="apply", permission_classes=[permissions.IsAuthenticated])
    def apply(self, request):
        devotee = getattr(request.user, "devotee_profile", None)
        if not devotee:
            return Response({"detail": "Only devotees can apply to become volunteers."}, status=400)

        existing = Volunteer.objects.filter(devotee=devotee).first()
        if existing and existing.status not in (
            Volunteer.Status.VOLUNTEER_REJECTED,
            Volunteer.Status.ADMIN_REJECTED,
            Volunteer.Status.AUTO_REJECTED,
        ):
            return Response(
                {"detail": f"You already have an application in progress (status: {existing.get_status_display()})."},
                status=400,
            )

        serializer = VolunteerApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        reference = data.get("reference_volunteer")

        with transaction.atomic():
            if existing:
                volunteer = existing
                volunteer.name = data["name"]
                volunteer.email = data["email"]
                volunteer.phone = data["phone"]
                volunteer.reference_volunteer = reference
                volunteer.status = Volunteer.Status.PENDING_VOLUNTEER_APPROVAL
                volunteer.is_volunteer = False
                volunteer.public_id = None
                if not volunteer.volunteer_code:
                    from .models import generate_volunteer_code
                    volunteer.volunteer_code = generate_volunteer_code()
                volunteer.save()

                Verification.objects.filter(volunteer=volunteer).delete()
                VolunteerApproval.objects.filter(volunteer=volunteer).delete()
            else:
                volunteer = Volunteer.objects.create(
                    devotee=devotee, user=request.user,
                    name=data["name"], email=data["email"], phone=data["phone"],
                    reference_volunteer=reference,
                    status=Volunteer.Status.PENDING_VOLUNTEER_APPROVAL,
                )

            Verification.objects.create(
                volunteer=volunteer,
                aadhaar_number=data.get("document_number", ""),
                aadhaar_front=data.get("document_front"),
                aadhaar_back=data.get("document_back"),
                live_photo=data.get("selfie"),
            )
            AuditLog.objects.create(
                volunteer=volunteer,
                action="devotee_reapplied" if existing else "devotee_applied",
                actor=request.user,
            )

            if reference:
                VolunteerApproval.objects.create(volunteer=volunteer, reference_volunteer=reference)
                AuditLog.objects.create(volunteer=volunteer, action="reference_selected", actor=request.user,
                                         detail=f"Reference: {reference.name}")

        if reference:
            notify_reference_required(reference, volunteer)
        notify_admins_new_application(volunteer)

        return Response({
            "id": volunteer.id,
            "volunteer_code": volunteer.volunteer_code,
            "status": volunteer.status,
            "message": "Application submitted. Document uploaded successfully.",
        }, status=201)

    @action(detail=False, methods=["post"], url_path="register", permission_classes=[IsApprovedVolunteer])
    def register(self, request):
        reference = request.user.volunteer_profile_v2
        serializer = VolunteerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data.get("reference_comment"):
            return Response({"detail": "Reference comment is required."}, status=400)

        with transaction.atomic():
            volunteer = Volunteer.objects.create(
                name=data["name"], email=data["email"], phone=data["phone"],
                profile_photo=data.get("profile_photo"),
                reference_volunteer=reference, created_by=request.user,
                status=Volunteer.Status.PENDING_VOLUNTEER_APPROVAL,
            )
            Verification.objects.create(
                volunteer=volunteer,
                aadhaar_number=data.get("aadhaar_number", ""), aadhaar_front=data.get("aadhaar_front"), aadhaar_back=data.get("aadhaar_back"),
                pan_number=data.get("pan_number", ""), pan_front=data.get("pan_front"), pan_back=data.get("pan_back"),
                license_number=data.get("license_number", ""), license_front=data.get("license_front"), license_back=data.get("license_back"),
                live_photo=data.get("live_photo"),
            )
            VolunteerApproval.objects.create(
                volunteer=volunteer, reference_volunteer=reference,
                reference_comment=data["reference_comment"],
            )
            AuditLog.objects.create(volunteer=volunteer, action="registered_with_reference", actor=request.user,
                                     detail=f"Reference: {reference.name}")

        notify_reference_required(reference, volunteer)
        notify_admins_new_application(volunteer)

        return Response(VolunteerDetailSerializer(volunteer, context=self.get_serializer_context()).data, status=201)

    @action(detail=True, methods=["post"], url_path="reference-action", permission_classes=[permissions.IsAuthenticated])
    def reference_action(self, request, pk=None):
        volunteer = self.get_object()
        approval = getattr(volunteer, "approval", None)
        if not approval:
            return Response({"detail": "No approval record."}, status=400)

        me = getattr(request.user, "volunteer_profile_v2", None)
        if not me or approval.reference_volunteer_id != me.id:
            return Response({"detail": "Not the reference volunteer for this application."}, status=403)
        if approval.reference_status != VolunteerApproval.RefStatus.PENDING:
            return Response({"detail": "Already actioned."}, status=400)

        serializer = ReferenceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data["action"]

        approval.reference_status = VolunteerApproval.RefStatus.APPROVED if act == "approve" else VolunteerApproval.RefStatus.REJECTED
        approval.reference_action_at = timezone.now()
        approval.save()

        volunteer.status = Volunteer.Status.VOLUNTEER_APPROVED if act == "approve" else Volunteer.Status.VOLUNTEER_REJECTED
        volunteer.save()

        AuditLog.objects.create(volunteer=volunteer, action=f"reference_{act}d", actor=request.user)

        for admin in User.objects.filter(is_staff=True):
            notify(admin, "Reference Decision Recorded",
                   f"Reference {'approved' if act == 'approve' else 'rejected'} {volunteer.name}.",
                   Notification.Type.STATUS_UPDATE, related_volunteer=volunteer)

        push_status_update(volunteer.id, {"volunteer_id": volunteer.id, "status": volunteer.status})
        return Response(VolunteerDetailSerializer(volunteer, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="admin-action", permission_classes=[permissions.IsAdminUser])
    def admin_action(self, request, pk=None):
        volunteer = self.get_object()
        approval = getattr(volunteer, "approval", None)

        serializer = AdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data["action"]
        override = serializer.validated_data["override"]
        reason = serializer.validated_data.get("reason", "")

        if act == "reject" and not reason:
            return Response({"detail": "A reason is required when rejecting an application."}, status=400)

        if approval:
            if approval.reference_status == VolunteerApproval.RefStatus.REJECTED and act == "approve" and not override:
                return Response({"detail": "Reference rejected. Set override=true to approve anyway."}, status=400)

            approval.admin_status = VolunteerApproval.AdminStatus.APPROVED if act == "approve" else VolunteerApproval.AdminStatus.REJECTED
            approval.admin_action_at = timezone.now()
            approval.admin_action_by = request.user
            approval.save()

        with transaction.atomic():
            if act == "approve":
                volunteer.status = Volunteer.Status.ADMIN_APPROVED
                volunteer.is_volunteer = True
                if not volunteer.public_id:
                    volunteer.public_id = VolunteerIdSequence.next_code()
            else:
                volunteer.status = Volunteer.Status.ADMIN_REJECTED
                volunteer.volunteer_code = None
            volunteer.save()

        if act == "approve" and volunteer.user and volunteer.user.user_type != User.UserType.VOLUNTEER:
            volunteer.user.user_type = User.UserType.VOLUNTEER
            volunteer.user.save(update_fields=["user_type"])

        AuditLog.objects.create(
            volunteer=volunteer, action=f"admin_{act}d", actor=request.user,
            detail=reason or ("override" if override else ""),
        )

        if volunteer.user:
            if act == "approve":
                notify(
                    volunteer.user, "Volunteer Application Approved", "approve",
                    Notification.Type.STATUS_UPDATE, related_volunteer=volunteer,
                )
            else:
                notify(
                    volunteer.user, "Volunteer Application Rejected", reason,
                    Notification.Type.STATUS_UPDATE, related_volunteer=volunteer,
                )

        push_status_update(volunteer.id, {
            "volunteer_id": volunteer.id,
            "status": volunteer.status,
            "public_id": volunteer.public_id,
            "reason": reason if act == "reject" else None,
        })

        if act == "approve":
            return Response({"id": volunteer.public_id, "message": "approve"}, status=200)
        return Response({"message": "rejected", "reason": reason}, status=200)

    @action(detail=True, methods=["get"], url_path="audit-log")
    def audit_log(self, request, pk=None):
        volunteer = self.get_object()
        logs = volunteer.audit_logs.select_related("actor")
        return Response(AuditLogSerializer(logs, many=True).data)


# -----------------------------------------------------------------------------
# Today's Duties
# -----------------------------------------------------------------------------
class DutyViewSet(viewsets.ModelViewSet):
    """
    Admin: full CRUD over all duties, plus a bulk `assign` action.

    Volunteer: sees only their own duties. Can `start` / `complete` /
    `request-help` (plain help or swap-with-a-named-volunteer) on their own
    duties. The volunteer named in a swap request sees the duty appear in
    their own `swap-respond` flow and can accept/decline it — accepting
    reassigns the duty to them.
    """

    queryset = Duty.objects.select_related("volunteer", "created_by", "swap_requested_with")
    serializer_class = DutySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["status", "priority", "volunteer", "duty_date"]
    search_fields = ["title", "duty_code", "volunteer__name"]
    ordering_fields = ["duty_date", "time", "created_at"]

    def get_serializer_class(self):
        if self.action == "assign":
            return DutyAssignSerializer
        if self.action == "request_help":
            return DutyHelpSerializer
        if self.action == "swap_respond":
            return DutySwapResponseSerializer
        return DutySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff or getattr(user, "user_type", None) == "admin":
            return qs
        vol = getattr(user, "volunteer_profile_v2", None)
        if not vol:
            return qs.none()
        # Include duties assigned to me, PLUS duties someone else wants to
        # swap onto me — otherwise the target volunteer can never see or
        # respond to (accept/decline) an incoming swap request.
        from django.db.models import Q
        return qs.filter(Q(volunteer=vol) | Q(swap_requested_with=vol))

    def perform_create(self, serializer):
        duty = serializer.save(created_by=self.request.user)
        notify_duty_assigned(duty)

    @action(detail=False, methods=["post"], url_path="assign", permission_classes=[permissions.IsAdminUser])
    def assign(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        volunteer_ids = data.pop("volunteer_ids")

        volunteers = Volunteer.objects.filter(id__in=volunteer_ids)
        if not volunteers.exists():
            return Response({"detail": "No matching volunteers found."}, status=400)

        created = []
        with transaction.atomic():
            for vol in volunteers:
                duty = Duty.objects.create(volunteer=vol, created_by=request.user, **data)
                created.append(duty)

        for duty in created:
            notify_duty_assigned(duty)

        return Response(DutySerializer(created, many=True).data, status=201)

    # -------- Volunteer: accept a newly assigned duty --------
    @action(detail=True, methods=["post"], url_path="accept", permission_classes=[permissions.IsAuthenticated])
    def accept(self, request, pk=None):
        duty = self.get_object()
        me = getattr(request.user, "volunteer_profile_v2", None)
        if not me or duty.volunteer_id != me.id:
            return Response({"detail": "This duty is not assigned to you."}, status=403)
        if duty.status != Duty.Status.ASSIGNED:
            return Response({"detail": "Only newly assigned duties can be accepted."}, status=400)
        duty.status = Duty.Status.ACCEPTED
        duty.accepted_at = timezone.now()
        duty.save(update_fields=["status", "accepted_at", "updated_at"])
        notify_duty_accepted(duty)
        return Response(DutySerializer(duty).data)

    @action(detail=True, methods=["post"], url_path="start", permission_classes=[permissions.IsAuthenticated])
    def start(self, request, pk=None):
        duty = self.get_object()
        if duty.status == Duty.Status.COMPLETED:
            return Response({"detail": "This duty is already completed."}, status=400)
        if duty.status == Duty.Status.ASSIGNED:
            return Response({"detail": "Accept this duty before starting it."}, status=400)
        duty.status = Duty.Status.IN_PROGRESS
        duty.started_at = duty.started_at or timezone.now()
        duty.save(update_fields=["status", "started_at", "updated_at"])
        return Response(DutySerializer(duty).data)

    @action(detail=True, methods=["post"], url_path="complete", permission_classes=[permissions.IsAuthenticated])
    def complete(self, request, pk=None):
        duty = self.get_object()
        duty.status = Duty.Status.COMPLETED
        duty.completed_at = timezone.now()
        duty.save(update_fields=["status", "completed_at", "updated_at"])
        notify_duty_completed(duty)
        return Response(DutySerializer(duty).data)

    # -------- Volunteer: request help, or request a swap with a named volunteer --------
    @action(detail=True, methods=["post"], url_path="request-help", permission_classes=[permissions.IsAuthenticated])
    def request_help(self, request, pk=None):
        duty = self.get_object()
        if duty.status == Duty.Status.COMPLETED:
            return Response({"detail": "This duty is already completed."}, status=400)
        if duty.status == Duty.Status.SWAP_REQUESTED:
            return Response({"detail": "A swap is already pending on this duty."}, status=400)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        swap_with = data.get("swap_with")

        if swap_with:
            if swap_with.id == duty.volunteer_id:
                return Response({"detail": "Cannot swap a duty with yourself."}, status=400)

            duty.pre_swap_status = duty.status  # remember state to restore on decline
            duty.status = Duty.Status.SWAP_REQUESTED
            duty.swap_requested_with = swap_with
            duty.swap_requested_at = timezone.now()
            duty.help_note = data.get("note", "")
            duty.save(update_fields=[
                "status", "pre_swap_status", "swap_requested_with",
                "swap_requested_at", "help_note", "updated_at",
            ])
            notify_duty_swap_requested(duty)
        else:
            duty.status = Duty.Status.HELP_REQUESTED
            duty.help_note = data.get("note", "")
            duty.save(update_fields=["status", "help_note", "updated_at"])
            notify_duty_help_requested(duty)

        return Response(DutySerializer(duty).data)

    # -------- Target volunteer: accept/decline a swap request --------
    @action(detail=True, methods=["post"], url_path="swap-respond", permission_classes=[permissions.IsAuthenticated])
    def swap_respond(self, request, pk=None):
        duty = self.get_object()

        if duty.status != Duty.Status.SWAP_REQUESTED or not duty.swap_requested_with_id:
            return Response({"detail": "No pending swap request on this duty."}, status=400)

        me = getattr(request.user, "volunteer_profile_v2", None)
        if not me or duty.swap_requested_with_id != me.id:
            return Response({"detail": "You are not the volunteer requested for this swap."}, status=403)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        act = serializer.validated_data["action"]

        original_volunteer = duty.volunteer
        target_volunteer = duty.swap_requested_with

        if act == "accept":
            duty.volunteer = target_volunteer
            duty.status = Duty.Status.ACCEPTED
            duty.accepted_at = timezone.now()
            duty.started_at = None
            duty.completed_at = None
            duty.help_note = ""
            duty.swap_requested_with = None
            duty.swap_requested_at = None
            duty.pre_swap_status = None
            duty.save(update_fields=[
                "volunteer", "status", "accepted_at", "started_at", "completed_at", "help_note",
                "swap_requested_with", "swap_requested_at", "pre_swap_status", "updated_at",
            ])
        else:
            duty.status = duty.pre_swap_status or Duty.Status.ASSIGNED
            duty.swap_requested_with = None
            duty.swap_requested_at = None
            duty.pre_swap_status = None
            duty.save(update_fields=[
                "status", "swap_requested_with", "swap_requested_at", "pre_swap_status", "updated_at",
            ])

        AuditLog.objects.create(
            volunteer=original_volunteer, action=f"duty_swap_{act}ed", actor=request.user,
            detail=f"Duty {duty.duty_code} — swap with {target_volunteer.name}",
        )

        notify_duty_swap_responded(duty, original_volunteer, target_volunteer, act)

        return Response(DutySerializer(duty).data)

    # -------- Dropdown data: who can this duty be swapped with --------
    @action(detail=True, methods=["get"], url_path="swap-candidates", permission_classes=[permissions.IsAuthenticated])
    def swap_candidates(self, request, pk=None):
        duty = self.get_object()
        candidates = Volunteer.objects.filter(
            is_volunteer=True,
            status=Volunteer.Status.ADMIN_APPROVED,
        ).exclude(id=duty.volunteer_id)
        return Response(SwapCandidateSerializer(candidates, many=True).data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response(NotificationSerializer(notif).data)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"count": count})