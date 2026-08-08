from django.contrib.auth import get_user_model
from devotees.models import Devotee
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets

from .models import (
    Attendance, CrowdStatus, CrowdThresholds, DevoteeQRStatus, ManualCounter,
    MealCollection, ScanHistory, VolunteerAreaAssignment,
)
from .permissions import IsAdminOrVolunteer, IsAdminUser, IsDevoteeUser, IsVolunteerUser
from .qr_generator import build_devotee_entry_qr, build_devotee_meal_qr, build_volunteer_qr, QR_VALIDITY_SECONDS
from .serializers import (
    AttendanceSerializer, CrowdStatusSerializer, CrowdThresholdsSerializer,
    ManualCheckinRequestSerializer, ManualCounterRequestSerializer, ManualCounterSerializer,
    ManualCounterSummarySerializer, ScanHistorySerializer, ScanQRRequestSerializer,
    VerifyVolunteerRequestSerializer, VolunteerAreaAssignmentSerializer,
    VolunteerAreaAssignmentUpsertSerializer, VolunteerCrowdStatusSerializer,
)
from .utils import QRDecryptionError, QRExpiredError, QRInvalidError, decrypt_payload

MANUAL_FLOW_TTL_SECONDS = 900  # how long a volunteer's fallback-auth stays usable
# Bumped from 300s -> 900s (15 min). 5 minutes was too tight for the real
# handoff: one volunteer opens "My QR" on their phone, then a second
# volunteer has to locate a scanning device and scan it. This is still a
# short-lived, single-purpose token (not a session credential), so 15 min
# keeps the security intent while matching realistic field conditions.


def _print_block(title: str, lines: list[str]) -> None:
    """Matches the exact terminal-log format requested: a title line,
    key:value pairs, and '====' separators top and bottom."""
    bar = "=" * 60
    print(f"\n{bar}\n{title}\n{bar}")
    for line in lines:
        print(line)
    print(bar)


def _validate_booking_reference(devotee, booking_reference: str) -> bool:
    """'booking valid (if present)' — only checked when the QR payload
    actually carries a booking_reference; a devotee QR with none is fine."""
    if not booking_reference:
        return True
    return devotee.bookings.filter(reference=booking_reference).exists()


def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR")


def _log_scan(*, encrypted_qr="", user_type="", devotee=None, volunteer=None, scan_method="QR",
              action_type="", booking_reference="", scan_status, device_ip, response_message):
    ScanHistory.objects.create(
        encrypted_qr=encrypted_qr, user_type=user_type, devotee=devotee, volunteer=volunteer,
        scan_method=scan_method, action_type=action_type, booking_reference=booking_reference,
        scan_status=scan_status, device_ip=device_ip, response_message=response_message,
    )


def _next_check_type(devotee) -> str:
    """Toggle based on the devotee's actual last successful Attendance row —
    this is the ONLY source of truth for CHECK_IN vs CHECK_OUT. The QR
    payload's action_type is never consulted here, and the Temple Entry QR
    never changes — that's exactly why this lookup exists."""
    last = Attendance.objects.filter(devotee=devotee, status=Attendance.SUCCESS).order_by("-timestamp").first()
    if last and last.check_type == Attendance.CHECK_IN:
        return Attendance.CHECK_OUT
    return Attendance.CHECK_IN


def _record_attendance(*, devotee, volunteer, scan_method, location, booking_reference, remarks=""):
    check_type = _next_check_type(devotee)
    return Attendance.objects.create(
        devotee=devotee, volunteer=volunteer, check_type=check_type, scan_method=scan_method,
        booking_reference=booking_reference, location=location, remarks=remarks,
    )


# ===========================================================================
# QR ATTENDANCE + MEAL SYSTEM (encrypted QR only)
# ===========================================================================

class ScanQRView(APIView):
    """POST /api/scan-qr/  { "encrypted_data": "gAAAAAB...." }

    The ONE endpoint Flutter ever calls, for BOTH devotee QR codes. Flutter
    never decrypts, inspects, or decides anything — it just forwards the
    raw string. This view decrypts it, then routes on the payload's
    action_type:

      - "entry" (or anything that isn't "meal", for backward compatibility
        with any already-issued QR) -> temple entry/exit flow, check-in vs
        check-out decided from Attendance history.
      - "meal" -> meal collection flow, completely separate from Attendance.
    """
    permission_classes = [IsVolunteerUser]

    def post(self, request):
        serializer = ScanQRRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        encrypted_data = serializer.validated_data["encrypted_data"]
        ip = _client_ip(request)

        _print_block("QR Scan Request Received", [f"Encrypted QR   : {encrypted_data}"])

        # Decrypt — max_age_seconds=QR_VALIDITY_SECONDS because both devotee
        # QR codes now rotate: a code older than this window is rejected as
        # QR Expired (handled by the QRExpiredError branch below).
        try:
            payload = decrypt_payload(encrypted_data, max_age_seconds=QR_VALIDITY_SECONDS)
        except QRInvalidError:
            _log_scan(encrypted_qr=encrypted_data, scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="Invalid QR")
            _print_block("QR Decryption Failed", ["Reason : Invalid QR (bad signature or tampered)"])
            return Response({"status": "failed", "message": "Invalid QR"}, status=status.HTTP_400_BAD_REQUEST)
        except QRExpiredError:
            _log_scan(encrypted_qr=encrypted_data, scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="QR Expired")
            _print_block("QR Decryption Failed", ["Reason : QR Expired"])
            return Response({"status": "failed", "message": "QR Expired"}, status=status.HTTP_400_BAD_REQUEST)
        except QRDecryptionError as exc:
            _log_scan(encrypted_qr=encrypted_data, scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message=str(exc))
            _print_block("QR Decryption Failed", [f"Reason : {exc}"])
            return Response({"status": "failed", "message": "QR Verification Failed"}, status=status.HTTP_400_BAD_REQUEST)

        _print_block("QR Decrypted Successfully", [
            f"User Type          : {payload.get('user_type')}",
            f"Devotee ID         : {payload.get('devotee_id')}",
            f"QR Purpose         : {payload.get('action_type')}",
            f"Booking Reference  : {payload.get('booking_reference', '')}",
        ])

        if payload["user_type"] != "devotee":
            _log_scan(encrypted_qr=encrypted_data, user_type=payload["user_type"],
                       scan_status=ScanHistory.FAILED, device_ip=ip,
                       response_message="Volunteer QR cannot be used for attendance/meal.")
            return Response(
                {"status": "failed", "message": "This is a volunteer QR — it can't be used here."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            devotee = Devotee.objects.get(pk=payload["devotee_id"])
        except Devotee.DoesNotExist:
            _log_scan(encrypted_qr=encrypted_data, user_type="devotee", scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="Devotee not found.")
            return Response({"status": "failed", "message": "Devotee Not Found"}, status=status.HTTP_404_NOT_FOUND)

        if getattr(devotee, "status", "active") != "active":
            _log_scan(encrypted_qr=encrypted_data, user_type="devotee", devotee=devotee,
                       scan_status=ScanHistory.FAILED, device_ip=ip, response_message="Devotee inactive/blocked.")
            return Response({"status": "failed", "message": "Devotee Blocked"}, status=status.HTTP_403_FORBIDDEN)

        if payload.get("action_type") == "meal":
            return self._handle_meal_scan(devotee, payload, request, encrypted_data, ip)
        return self._handle_entry_scan(devotee, payload, request, encrypted_data, ip)

    # -- Temple Entry QR: check-in / check-out ---------------------------
    def _handle_entry_scan(self, devotee, payload, request, encrypted_data, ip):
        booking_reference = payload.get("booking_reference", "")
        if booking_reference and not _validate_booking_reference(devotee, booking_reference):
            _log_scan(encrypted_qr=encrypted_data, user_type="devotee", devotee=devotee,
                       scan_status=ScanHistory.FAILED, device_ip=ip,
                       response_message=f"Booking reference {booking_reference} not found for devotee.")
            return Response({"status": "failed", "message": "Invalid Booking Reference"}, status=status.HTTP_400_BAD_REQUEST)

        attendance = _record_attendance(
            devotee=devotee, volunteer=request.user, scan_method=Attendance.QR,
            location=payload.get("location", ""), booking_reference=booking_reference,
        )

        _log_scan(encrypted_qr=encrypted_data, user_type="devotee", devotee=devotee, volunteer=request.user,
                   scan_method="QR", action_type=attendance.check_type,
                   booking_reference=attendance.booking_reference, scan_status=ScanHistory.SUCCESS,
                   device_ip=ip, response_message=f"{attendance.check_type} recorded.")

        _print_block("Attendance Recorded", [
            f"Devotee            : {devotee.full_name}",
            f"Action             : {attendance.check_type}",
            "Attendance Saved   : Yes",
            "Scan History Saved : Yes",
        ])

        return Response({
            "status": "success",
            "message": f"{attendance.check_type.replace('_', ' ').title()} Successful",
            "devotee_name": devotee.full_name,
            "devotee_id": devotee.id,
            "booking_reference": attendance.booking_reference,
            "check_type": attendance.check_type,
            "scan_time": attendance.timestamp,
        }, status=status.HTTP_200_OK)

    # -- Meal QR: meal collection -----------------------------------------
    def _handle_meal_scan(self, devotee, payload, request, encrypted_data, ip):
        if MealCollection.already_collected_today(devotee):
            _log_scan(encrypted_qr=encrypted_data, user_type="devotee", devotee=devotee, volunteer=request.user,
                       scan_method="QR", action_type="MEAL", scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="Meal already collected today.")
            return Response({
                "status": "failed",
                "message": "Meal Already Collected Today",
                "devotee_name": devotee.full_name,
                "devotee_id": devotee.id,
            }, status=status.HTTP_400_BAD_REQUEST)

        meal = MealCollection.objects.create(
            devotee=devotee, volunteer=request.user, location=payload.get("location", ""),
        )

        _log_scan(encrypted_qr=encrypted_data, user_type="devotee", devotee=devotee, volunteer=request.user,
                   scan_method="QR", action_type="MEAL", scan_status=ScanHistory.SUCCESS,
                   device_ip=ip, response_message="Meal collected.")

        _print_block("Meal Collected", [
            f"Devotee            : {devotee.full_name}",
            "Meal Collection Saved : Yes",
            "Scan History Saved    : Yes",
        ])

        return Response({
            "status": "success",
            "message": "Meal Collected Successfully",
            "devotee_name": devotee.full_name,
            "devotee_id": devotee.id,
            "scan_time": meal.timestamp,
        }, status=status.HTTP_200_OK)


class VerifyVolunteerView(APIView):
    """POST /api/verify-volunteer/  { "encrypted_data": "..." }

    Decrypts the volunteer's own QR and confirms three things: it's a
    volunteer QR (not a devotee QR), the volunteer account still exists
    and is active, and the QR belongs to the currently logged-in volunteer
    (this last check is what makes it safe to hand back a `volunteer_token`
    that ManualCheckinView will trust later).

    `payload["volunteer_id"]` is now a volunteers.models.Volunteer.pk (not
    a User.pk) — see build_volunteer_qr in qr_generator.py — so the lookup
    below goes through Volunteer, and the "belongs to logged-in volunteer"
    check compares volunteer.user_id against request.user.id.

    DIAGNOSTIC PATCH: the decrypt step below now catches QRInvalidError and
    QRExpiredError separately (same pattern as ScanQRView) instead of one
    generic QRDecryptionError, so ScanHistory.response_message and the
    returned `message` field reveal whether a 400 was caused by a bad/
    tampered signature vs. an expired token (most likely: the volunteer QR
    is minted fresh on every /volunteers/me/qr-data/ call and only valid
    for MANUAL_FLOW_TTL_SECONDS = 300s). Response shape, status codes, and
    the "error" vocabulary are all otherwise unchanged.
    """
    permission_classes = [IsVolunteerUser]

    def post(self, request):
        serializer = VerifyVolunteerRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        encrypted_data = serializer.validated_data["encrypted_data"]
        ip = _client_ip(request)

        try:
            payload = decrypt_payload(encrypted_data)
        except QRInvalidError:
            _log_scan(encrypted_qr=encrypted_data, scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="Invalid QR (bad signature or tampered).")
            return Response({"status": "error", "message": "Invalid QR"}, status=status.HTTP_400_BAD_REQUEST)
        except QRExpiredError:
            _log_scan(encrypted_qr=encrypted_data, scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="QR Expired (older than MANUAL_FLOW_TTL_SECONDS).")
            return Response({"status": "error", "message": "QR Expired"}, status=status.HTTP_400_BAD_REQUEST)
        except QRDecryptionError as exc:
            _log_scan(encrypted_qr=encrypted_data, scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message=str(exc))
            return Response({"status": "error", "message": "Volunteer QR could not be verified."},
                              status=status.HTTP_400_BAD_REQUEST)

        if payload["user_type"] != "volunteer":
            _log_scan(encrypted_qr=encrypted_data, user_type=payload.get("user_type", ""),
                       scan_status=ScanHistory.FAILED, device_ip=ip,
                       response_message="Devotee QR cannot be used for volunteer verification.")
            return Response({"status": "error", "message": "This is a devotee QR — it can't be used here."},
                              status=status.HTTP_400_BAD_REQUEST)

        from volunteers.models import Volunteer
        try:
            volunteer = Volunteer.objects.select_related("user").get(id=payload["volunteer_id"])
        except Volunteer.DoesNotExist:
            _log_scan(encrypted_qr=encrypted_data, user_type="volunteer", scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="Volunteer not found.")
            return Response({"status": "error", "message": "Volunteer Not Found"}, status=status.HTTP_404_NOT_FOUND)

        if not volunteer.user.is_active:
            _log_scan(encrypted_qr=encrypted_data, user_type="volunteer", volunteer=volunteer.user,
                       scan_status=ScanHistory.FAILED, device_ip=ip, response_message="Volunteer inactive.")
            return Response({"status": "error", "message": "Volunteer Inactive"}, status=status.HTTP_403_FORBIDDEN)

        if volunteer.user_id != request.user.id:
            _log_scan(encrypted_qr=encrypted_data, user_type="volunteer", volunteer=volunteer.user,
                       scan_status=ScanHistory.FAILED, device_ip=ip,
                       response_message="QR does not belong to the logged-in volunteer.")
            return Response({"status": "error", "message": "This QR does not match your account."},
                              status=status.HTTP_403_FORBIDDEN)

        _log_scan(encrypted_qr=encrypted_data, user_type="volunteer", volunteer=volunteer.user,
                   scan_status=ScanHistory.SUCCESS, device_ip=ip, response_message="Volunteer verified.")

        role = payload.get("role") or getattr(volunteer, "role", "") or ""
        return Response({
            "status": "success",
            "volunteer_id": volunteer.id,
            "volunteer_name": volunteer.user.get_full_name() or getattr(volunteer.user, "username", ""),
            "role": role,
            "message": "Volunteer Verified",
            # Kept for backward compatibility: ManualCheckinView re-verifies
            # this token server-side rather than trusting that this step ran.
            "volunteer_token": encrypted_data,
        })


class DevoteeSearchView(APIView):
    """GET /api/devotees/search/?q=...  — Manual Search Screen, fallback step 2."""
    permission_classes = [IsVolunteerUser]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"results": []})
        matches = Devotee.objects.filter(
            Q(devotee_code__iexact=q) | Q(phone__icontains=q) | Q(full_name__icontains=q)
        )[:10]
        return Response({"results": [
            {"id": d.id, "name": d.full_name, "phone": d.phone, "devotee_code": d.devotee_code}
            for d in matches
        ]})


class ManualCheckinView(APIView):
    """POST /api/manual-checkin/ — fallback step 3. Re-verifies volunteer_token
    server-side rather than trusting the client's word that step 1 happened.

    `payload["volunteer_id"]` is a Volunteer.pk now, so the "does this token
    belong to the logged-in user" check goes through Volunteer.objects.get(
    id=..., user=request.user) rather than comparing ids directly.

    max_age_seconds=MANUAL_FLOW_TTL_SECONDS is intentionally kept here even
    though the underlying volunteer QR is otherwise treated as long-lived —
    this token is the sole time-bound guard on the manual-checkin bypass
    path, and removing it would turn a leaked/photographed volunteer QR
    into a standing credential instead of one valid for 15 minutes.
    """
    permission_classes = [IsVolunteerUser]

    def post(self, request):
        serializer = ManualCheckinRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ip = _client_ip(request)

        try:
            payload = decrypt_payload(data["volunteer_token"], max_age_seconds=MANUAL_FLOW_TTL_SECONDS)
        except QRDecryptionError:
            return Response({"status": "error", "message": "Volunteer session expired — scan your QR again."},
                              status=status.HTTP_400_BAD_REQUEST)

        if payload["user_type"] != "volunteer":
            return Response({"status": "error", "message": "Volunteer verification does not match your account."},
                              status=status.HTTP_403_FORBIDDEN)

        from volunteers.models import Volunteer
        try:
            Volunteer.objects.get(id=payload["volunteer_id"], user=request.user)
        except Volunteer.DoesNotExist:
            return Response({"status": "error", "message": "Volunteer verification does not match your account."},
                              status=status.HTTP_403_FORBIDDEN)

        devotee_qs = Devotee.objects.all()
        if data.get("devotee_id"):
            devotee_qs = devotee_qs.filter(pk=data["devotee_id"])
        elif data.get("booking_reference"):
            devotee_qs = devotee_qs.filter(bookings__reference=data["booking_reference"])
        elif data.get("mobile"):
            devotee_qs = devotee_qs.filter(phone=data["mobile"])
        else:
            devotee_qs = devotee_qs.filter(full_name__icontains=data["name"])

        devotee = devotee_qs.first()
        if not devotee:
            _log_scan(user_type="devotee", scan_method="MANUAL", scan_status=ScanHistory.FAILED,
                       device_ip=ip, response_message="No matching devotee for manual check-in.")
            return Response({"status": "error", "message": "No matching devotee found."}, status=status.HTTP_404_NOT_FOUND)

        attendance = _record_attendance(
            devotee=devotee, volunteer=request.user, scan_method=Attendance.MANUAL,
            location=data.get("location", ""), booking_reference=data.get("booking_reference", ""),
            remarks=data.get("remarks", ""),
        )
        _log_scan(user_type="devotee", devotee=devotee, volunteer=request.user, scan_method="MANUAL",
                   action_type=attendance.check_type, booking_reference=attendance.booking_reference,
                   scan_status=ScanHistory.SUCCESS, device_ip=ip,
                   response_message=f"Manual {attendance.check_type} recorded.")

        return Response({
            "status": "success",
            "message": f"{attendance.check_type.replace('_', ' ').title()} Successful (Manual)",
            "devotee_name": devotee.full_name,
            "booking_reference": attendance.booking_reference,
            "check_type": attendance.check_type,
        })


class DevoteeMyQRView(APIView):
    """GET /api/devotees/me/qr-data/ — returns the devotee's TWO ROTATING
    QR codes. Each GET mints a fresh encrypted token for both entry and
    meal QR (fresh Fernet timestamp baked in via encrypt_payload), valid
    for QR_VALIDITY_SECONDS. ScanQRView enforces that same window on the
    scan side via decrypt_payload(..., max_age_seconds=QR_VALIDITY_SECONDS).

    DevoteeQRStatus's stored entry_qr_token/meal_qr_token are no longer
    read here — they were only ever a snapshot from signup and would
    defeat rotation if served back as-is. (See caller's note: check
    whether anything else in the codebase still reads DevoteeQRStatus
    directly — an admin screen, reissue endpoint, export, etc. — since
    that would keep showing the old permanent code out of sync with this
    view.)
    """
    permission_classes = [IsDevoteeUser]

    def get(self, request):
        devotee = getattr(request.user, "devotee_profile", None)
        if not devotee:
            return Response({"detail": "Your account isn't linked to a devotee profile."}, status=status.HTTP_403_FORBIDDEN)

        entry_token, entry_image = build_devotee_entry_qr(devotee)
        meal_token, meal_image = build_devotee_meal_qr(devotee)

        return Response({
            "entry_qr": {
                "label": "Temple Entry QR",
                "purpose": "Used for Temple Entry & Exit",
                "qr_data": entry_token,
                "qr_image": entry_image,
            },
            "meal_qr": {
                "label": "Meal QR",
                "purpose": "Used for Meal Collection",
                "qr_data": meal_token,
                "qr_image": meal_image,
            },
        })


class VolunteerMyQRView(APIView):
    """GET /api/volunteers/me/qr-data/ — volunteer's own identity/fallback-auth
    QR. The token now carries user_type, volunteer_id (Volunteer.pk), role,
    location (from the volunteer's area assignment, if any), and
    generated_at — verified against MANUAL_FLOW_TTL_SECONDS in
    VerifyVolunteerView/ManualCheckinView.

    Looks up the Volunteer row for request.user, since build_volunteer_qr
    now expects a Volunteer instance rather than the User.
    """
    permission_classes = [IsVolunteerUser]

    def get(self, request):
        from volunteers.models import Volunteer
        try:
            volunteer = Volunteer.objects.get(user=request.user)
        except Volunteer.DoesNotExist:
            return Response({"detail": "Your account isn't linked to a volunteer profile."}, status=status.HTTP_403_FORBIDDEN)

        token, image = build_volunteer_qr(volunteer)
        return Response({"qr_data": token, "qr_image": image})


class AttendanceListView(APIView):
    """GET /api/attendance/?devotee_id=&date=&check_type=&scan_method="""
    permission_classes = [IsAdminOrVolunteer]

    def get(self, request):
        qs = Attendance.objects.select_related("devotee", "volunteer").all()
        for param, field in [("devotee_id", "devotee_id"), ("date", "timestamp__date"),
                               ("check_type", "check_type"), ("scan_method", "scan_method")]:
            val = request.query_params.get(param)
            if val:
                qs = qs.filter(**{field: val})
        return Response(AttendanceSerializer(qs[:200], many=True).data)


class ScanHistoryListView(APIView):
    """GET /api/scan-history/ — raw audit log, admin/volunteer only."""
    permission_classes = [IsAdminOrVolunteer]

    def get(self, request):
        qs = ScanHistory.objects.select_related("devotee", "volunteer").all()[:200]
        return Response(ScanHistorySerializer(qs, many=True).data)


# ===========================================================================
# Crowd-density dashboard — separate feature, kept as-is per spec
# ===========================================================================

class AdminCrowdStatusViewSet(viewsets.ModelViewSet):
    queryset = CrowdStatus.objects.select_related("updated_by").all()
    serializer_class = CrowdStatusSerializer
    permission_classes = [IsAdminUser]

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)


class VolunteerCrowdStatusView(APIView):
    permission_classes = [IsVolunteerUser]

    def post(self, request):
        try:
            assignment = request.user.area_assignment
        except VolunteerAreaAssignment.DoesNotExist:
            return Response({"detail": "You are not assigned to an area yet. Contact an admin."},
                              status=status.HTTP_403_FORBIDDEN)
        instance, _ = CrowdStatus.objects.get_or_create(assigned_area=assignment.assigned_area)
        serializer = VolunteerCrowdStatusSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user, assigned_area=assignment.assigned_area)
        return Response(CrowdStatusSerializer(instance).data)


class MyAreaCrowdStatusView(APIView):
    permission_classes = [IsVolunteerUser]

    def get(self, request):
        try:
            assignment = request.user.area_assignment
        except VolunteerAreaAssignment.DoesNotExist:
            return Response({"detail": "You are not assigned to an area yet."}, status=status.HTTP_404_NOT_FOUND)
        instance = CrowdStatus.objects.filter(assigned_area=assignment.assigned_area).first()
        if not instance:
            return Response({"detail": "No status recorded yet for your area."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CrowdStatusSerializer(instance).data)


class CrowdThresholdsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(CrowdThresholdsSerializer(CrowdThresholds.load()).data)

    def put(self, request):
        instance = CrowdThresholds.load()
        serializer = CrowdThresholdsSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ===========================================================================
# Manual Counter — volunteers bump the count when a devotee enters without
# scanning (QR broken, VIP entry, walk-in, etc). Area is always resolved
# from VolunteerAreaAssignment, never from client input.
# ===========================================================================

class ManualCounterView(APIView):
    """GET/POST /api/manual-counter/ — Volunteer-only.

    GET  -> summary for the volunteer's own area: current running total
            (increments minus decrements, floored at 0) plus today's
            increment/decrement totals for the "+40 / -15" style display.
    POST -> record one +/- action and return the updated running total.

    Area assignment is no longer required for this feature — a volunteer
    with no VolunteerAreaAssignment falls back to DEFAULT_AREA instead of
    getting a 403. (Crowd Status still requires an assignment; that check
    is untouched.)
    """
    permission_classes = [IsVolunteerUser]

    DEFAULT_AREA = "General"

    def _get_area(self, request):
        try:
            return request.user.area_assignment.assigned_area
        except VolunteerAreaAssignment.DoesNotExist:
            return self.DEFAULT_AREA

    def get(self, request):
        area = self._get_area(request)
        data = {
            "current_manual_count": ManualCounter.current_count_for_area(area),
            **ManualCounter.today_stats_for_area(area),
        }
        return Response(ManualCounterSummarySerializer(data).data)

    def post(self, request):
        area = self._get_area(request)

        serializer = ManualCounterRequestSerializer(data=request.data)

        serializer = ManualCounterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action_in = serializer.validated_data["action"]
        requested_count = serializer.validated_data["count"]
        reason = serializer.validated_data.get("reason", "")
        model_action = ManualCounter.INCREMENT if action_in == "increment" else ManualCounter.DECREMENT

        if model_action == ManualCounter.DECREMENT:
            # Never let the running total go below zero, regardless of what
            # the app sends — clamp to whatever's actually available.
            current = ManualCounter.current_count_for_area(area)
            if current <= 0:
                return Response({
                    "status": "failed",
                    "message": "Manual count is already zero — cannot decrement further.",
                    "current_manual_count": 0,
                }, status=status.HTTP_400_BAD_REQUEST)
            requested_count = min(requested_count, current)

        entry = ManualCounter.objects.create(
            volunteer=request.user, assigned_area=area, action=model_action,
            count=requested_count, reason=reason,
        )

        return Response({
            "status": "success",
            "message": f"Manual count {action_in}ed by {requested_count}.",
            "current_manual_count": ManualCounter.current_count_for_area(area),
            "action": entry.action,
            "count": entry.count,
            "reason": entry.reason,
            "timestamp": entry.timestamp,
        }, status=status.HTTP_201_CREATED)


class ManualCounterAdminListView(APIView):
    """GET /api/manual-counter/admin/ — full audit trail for admins.
    Optional filters: ?area=&volunteer_id=&date=YYYY-MM-DD
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = ManualCounter.objects.select_related("volunteer").all()
        area = request.query_params.get("area")
        volunteer_id = request.query_params.get("volunteer_id")
        date = request.query_params.get("date")
        if area:
            qs = qs.filter(assigned_area=area)
        if volunteer_id:
            qs = qs.filter(volunteer_id=volunteer_id)
        if date:
            qs = qs.filter(timestamp__date=date)
        return Response(ManualCounterSerializer(qs[:200], many=True).data)


# ===========================================================================
# Volunteer Area Assignment — admin manages which single area each
# volunteer may report Crowd Status / Manual Counter for. Without this,
# a volunteer hits 403 on both features until someone sets it up in the
# Django shell/admin — this gives admins a UI for it instead.
# ===========================================================================

class AdminVolunteerListView(APIView):
    """GET /api/admin/volunteers-list/ — lightweight roster of every
    volunteer account, including their current area (or null), used to
    populate the 'Assign Area' screen."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        User = get_user_model()
        volunteers = (
            User.objects.filter(user_type="volunteer")
            .select_related("area_assignment")
            .order_by("username")
        )
        data = [
            {
                "id": v.id,
                "username": v.username,
                "name": v.get_full_name() or v.username,
                "assigned_area": getattr(v, "area_assignment", None) and v.area_assignment.assigned_area,
            }
            for v in volunteers
        ]
        return Response(data)


class AdminVolunteerAreaAssignmentView(APIView):
    """GET/POST/DELETE /api/admin/volunteer-areas/ — admin-only management
    of VolunteerAreaAssignment (a strict one-area-per-volunteer mapping,
    enforced by the model's OneToOneField).

    GET    -> every current assignment, for an audit/overview list.
    POST   -> {volunteer_id, assigned_area} upserts that volunteer's area.
              An empty assigned_area removes the assignment instead of
              being rejected, since clearing someone's area is a normal
              admin action (e.g. taking them off duty).
    DELETE -> {volunteer_id} removes that volunteer's assignment.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = VolunteerAreaAssignment.objects.select_related("volunteer").order_by("assigned_area")
        return Response(VolunteerAreaAssignmentSerializer(qs, many=True).data)

    def post(self, request):
        serializer = VolunteerAreaAssignmentUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        volunteer_id = serializer.validated_data["volunteer_id"]
        assigned_area = serializer.validated_data["assigned_area"].strip()

        User = get_user_model()
        try:
            volunteer = User.objects.get(pk=volunteer_id, user_type="volunteer")
        except User.DoesNotExist:
            return Response({"detail": "Volunteer not found."}, status=status.HTTP_404_NOT_FOUND)

        if not assigned_area:
            VolunteerAreaAssignment.objects.filter(volunteer=volunteer).delete()
            return Response({"detail": "Assignment removed."}, status=status.HTTP_200_OK)

        assignment, _ = VolunteerAreaAssignment.objects.update_or_create(
            volunteer=volunteer, defaults={"assigned_area": assigned_area},
        )
        return Response(VolunteerAreaAssignmentSerializer(assignment).data, status=status.HTTP_200_OK)

    def delete(self, request):
        volunteer_id = request.data.get("volunteer_id") or request.query_params.get("volunteer_id")
        if not volunteer_id:
            return Response({"detail": "volunteer_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = VolunteerAreaAssignment.objects.filter(volunteer_id=volunteer_id).delete()
        if not deleted:
            return Response({"detail": "No assignment found for this volunteer."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)