import base64, io
import qrcode
from django.utils import timezone
from .utils import encrypt_payload

QR_VALIDITY_SECONDS = 15  # >10s frontend refresh interval, buffer for scan/network lag


def _qr_png_data_uri(data: str) -> str:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def render_qr_image(token: str) -> str:
    """Render a PNG data-uri for an ALREADY-GENERATED, permanent token —
    used when serving a devotee's stored entry/meal QR back to them without
    re-encrypting or minting a new payload."""
    return _qr_png_data_uri(token)


def build_devotee_entry_qr(devotee):
    """Temple Entry QR — used for BOTH check-in and check-out. Built once
    (from DevoteeQRStatus.get_or_create_for_devotee) and stored forever.
    `action_type` here is a fixed marker, not a next-action instruction —
    /api/scan-qr/ uses it only to route to the attendance branch, never to
    decide CHECK_IN vs CHECK_OUT (that comes from Attendance history)."""
    payload = {
        "user_type": "devotee",
        "devotee_id": devotee.id,
        "location": "",
        "timestamp": timezone.now().isoformat(),
        "action_type": "entry",
        "booking_reference": "",
    }
    token = encrypt_payload(payload)
    return token, _qr_png_data_uri(token)


def build_devotee_meal_qr(devotee):
    """Meal QR — permanent, unrelated to attendance. `/api/scan-qr/` routes
    to meal-collection handling when it sees action_type == 'meal'."""
    payload = {
        "user_type": "devotee",
        "devotee_id": devotee.id,
        "location": "",
        "timestamp": timezone.now().isoformat(),
        "action_type": "meal",
        "booking_reference": "",
    }
    token = encrypt_payload(payload)
    return token, _qr_png_data_uri(token)


def build_volunteer_qr(volunteer, *, location: str = ""):
    """Volunteer identity QR — used both for /api/volunteers/me/qr-data/
    and as the fallback-auth step verified by VerifyVolunteerView /
    ManualCheckinView (still short-lived by design, checked against
    MANUAL_FLOW_TTL_SECONDS there).

    `volunteer` is a volunteers.models.Volunteer instance (not the User)
    — `volunteer_id` in the payload is Volunteer.pk. VolunteerAreaAssignment
    still links to AUTH_USER_MODEL, so the area lookup goes through
    volunteer.user.

    Payload carries user_type, volunteer_id, role, location (best-effort,
    from the volunteer's area assignment if one exists and none was passed
    explicitly), and generated_at.
    """
    if not location:
        from .models import VolunteerAreaAssignment  # local import: avoid any load-order coupling with models.py
        assignment = VolunteerAreaAssignment.objects.filter(volunteer=volunteer.user).first()
        location = assignment.assigned_area if assignment else ""
    role = getattr(volunteer, "role", "") or ""
    payload = {
        "user_type": "volunteer",
        "volunteer_id": volunteer.id,
        "role": role,
        "location": location,
        "generated_at": timezone.now().isoformat(),
    }
    token = encrypt_payload(payload)
    return token, _qr_png_data_uri(token)