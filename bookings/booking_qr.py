from crowd_status.utils import encrypt_payload


def build_seva_booking_qr(booking) -> str:
    """Encrypted payload for a confirmed Seva Booking. Reuses the exact same
    Fernet-based encrypt_payload() used by the Attendance/Entry/Meal QR
    system — this is a NEW payload shape (qr_type-based), not a variant of
    the devotee entry/meal QR, so it can never be confused with those at
    scan time."""
    payload = {
        "qr_type": "seva",
        "booking_id": booking.id,
        "booking_reference": booking.booking_code,
        "devotee_id": booking.devotee_id,
        "devotee_name": booking.devotee.full_name,
        "seva_name": booking.seva.name,
        "seva_date": booking.date.isoformat(),
        "seva_time": booking.slot,
        "status": "BOOKED",
    }
    return encrypt_payload(payload)


def build_meal_booking_qr(meal_booking) -> str:
    """Encrypted payload for a confirmed Meal Booking. Same encryption
    helper as build_seva_booking_qr — only the payload shape differs."""
    payload = {
        "qr_type": "meal",
        "booking_id": meal_booking.id,
        "booking_reference": meal_booking.booking_code,
        "devotee_id": meal_booking.devotee_id,
        "devotee_name": meal_booking.devotee.full_name,
        "meal_name": meal_booking.meal_name,
        "meal_date": meal_booking.meal_date.isoformat(),
        "meal_time": meal_booking.meal_time,
        "status": "BOOKED",
    }
    return encrypt_payload(payload)