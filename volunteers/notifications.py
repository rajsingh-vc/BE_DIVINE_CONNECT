from django.contrib.auth import get_user_model

from .models import Notification
from .realtime import push_notification


def notify(recipient_user, title, message, ntype, related_volunteer=None, related_incident=None, related_duty=None, related_sos=None):
    notif = Notification.objects.create(
        recipient=recipient_user, title=title, message=message,
        type=ntype, related_volunteer=related_volunteer, related_incident=related_incident,
        related_duty=related_duty, related_sos=related_sos,
    )
    push_notification(recipient_user.id, {
        "id": notif.id, "title": title, "message": message,
        "type": ntype, "volunteer_id": related_volunteer.id if related_volunteer else None,
        "incident_id": related_incident.id if related_incident else None,
        "duty_id": related_duty.id if related_duty else None,
        "sos_id": related_sos.id if related_sos else None,
        "created_at": notif.created_at.isoformat(),
    })
    return notif


def notify_reference_required(reference_volunteer, new_volunteer):
    if not reference_volunteer.user:
        return
    notify(
        reference_volunteer.user,
        "Volunteer Approval Required",
        f"You have been listed as the reference for {new_volunteer.name}. Please Approve or Reject this request.",
        Notification.Type.VOLUNTEER_APPROVAL_REQUIRED,
        related_volunteer=new_volunteer,
    )


def notify_admins_new_application(new_volunteer):
    User = get_user_model()
    admins = User.objects.filter(is_staff=True)
    for admin in admins:
        notify(
            admin, "New Volunteer Application",
            f"{new_volunteer.name} applied via reference {new_volunteer.reference_volunteer.name if new_volunteer.reference_volunteer else '—'}.",
            Notification.Type.NEW_VOLUNTEER_APPLICATION,
            related_volunteer=new_volunteer,
        )


# ---------------------------------------------------------------------------
# Duties — "Today's Duties" notifications
# ---------------------------------------------------------------------------

def _admins():
    User = get_user_model()
    return User.objects.filter(is_staff=True)


def notify_duty_assigned(duty):
    """Admin assigned a duty -> notify the volunteer."""
    if not duty.volunteer.user:
        return
    when = duty.time.strftime("%I:%M %p").lstrip("0") if duty.time else "today"
    notify(
        duty.volunteer.user,
        "New Duty Assigned",
        f"You've been assigned \"{duty.title}\" at {when}" + (f" — {duty.location}." if duty.location else "."),
        Notification.Type.DUTY_ASSIGNED,
        related_volunteer=duty.volunteer,
        related_duty=duty,
    )


def notify_duty_accepted(duty):
    """Volunteer accepted a newly assigned duty -> notify all admins."""
    for admin in _admins():
        notify(
            admin, "Duty Accepted",
            f"{duty.volunteer.name} accepted \"{duty.title}\".",
            Notification.Type.DUTY_STATUS_UPDATE,
            related_volunteer=duty.volunteer,
            related_duty=duty,
        )


def notify_duty_completed(duty):
    """Volunteer marked a duty complete -> notify all admins."""
    for admin in _admins():
        notify(
            admin, "Duty Completed",
            f"{duty.volunteer.name} completed \"{duty.title}\".",
            Notification.Type.DUTY_COMPLETED,
            related_volunteer=duty.volunteer,
            related_duty=duty,
        )


def notify_duty_help_requested(duty):
    """Volunteer tapped Swap/Help (plain help, no name picked) -> notify all admins."""
    for admin in _admins():
        notify(
            admin, "Duty Help Requested",
            f"{duty.volunteer.name} requested help on \"{duty.title}\"" + (f": {duty.help_note}" if duty.help_note else "."),
            Notification.Type.DUTY_HELP_REQUESTED,
            related_volunteer=duty.volunteer,
            related_duty=duty,
        )


def notify_duty_swap_requested(duty):
    """Volunteer picked a name from the swap dropdown -> notify that
    volunteer (to accept/decline) and all admins."""
    target = duty.swap_requested_with
    if target and target.user:
        notify(
            target.user,
            "Duty Swap Requested",
            f"{duty.volunteer.name} wants to swap \"{duty.title}\" with you. Accept or decline in your Duties tab.",
            Notification.Type.DUTY_HELP_REQUESTED,
            related_volunteer=duty.volunteer,
            related_duty=duty,
        )
    for admin in _admins():
        notify(
            admin,
            "Duty Swap Requested",
            f"{duty.volunteer.name} requested a swap on \"{duty.title}\" with {target.name if target else 'someone'}.",
            Notification.Type.DUTY_HELP_REQUESTED,
            related_volunteer=duty.volunteer,
            related_duty=duty,
        )


def notify_duty_swap_responded(duty, original_volunteer, target_volunteer, action):
    """Target volunteer accepted/declined a swap -> notify the original
    volunteer and all admins."""
    verb = "accepted" if action == "accept" else "declined"
    if original_volunteer.user:
        notify(
            original_volunteer.user,
            f"Duty Swap {verb.title()}",
            f"{target_volunteer.name} {verb} the swap for \"{duty.title}\".",
            Notification.Type.DUTY_SWAP_RESPONSE,
            related_volunteer=target_volunteer,
            related_duty=duty,
        )
    for admin in _admins():
        notify(
            admin,
            f"Duty Swap {verb.title()}",
            f"{target_volunteer.name} {verb} a swap request from {original_volunteer.name} on \"{duty.title}\".",
            Notification.Type.DUTY_SWAP_RESPONSE,
            related_volunteer=original_volunteer,
            related_duty=duty,
        )

def notify_volunteers_meal_session(session):
    """Admin created a meal session (gate + time window) -> notify every
    approved volunteer so they know a meal check-in window is open and can
    go scan the QR displayed at that gate."""
    from .models import Volunteer

    start = session.start_time.strftime("%I:%M %p").lstrip("0")
    end = session.end_time.strftime("%I:%M %p").lstrip("0")

    volunteers = Volunteer.objects.filter(
        is_volunteer=True,
        status=Volunteer.Status.ADMIN_APPROVED,
        user__isnull=False,
    ).select_related("user")

    for vol in volunteers:
        notify(
            vol.user,
            "Meal Session Open",
            f"Meal check-in is open at {session.location}, {start} – {end}. Scan the QR at the gate to check in.",
            Notification.Type.MEAL_SESSION_OPEN,
        )