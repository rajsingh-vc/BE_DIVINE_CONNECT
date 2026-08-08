from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Volunteer, VolunteerApproval, Notification, AuditLog
from .notifications import notify
from .realtime import push_status_update

User = get_user_model()


@shared_task
def auto_reject_expired_approvals():
    expired = VolunteerApproval.objects.filter(
        reference_status=VolunteerApproval.RefStatus.PENDING,
        deadline__lt=timezone.now(),
        auto_rejected=False,
    )
    for approval in expired:
        approval.reference_status = VolunteerApproval.RefStatus.AUTO_REJECTED
        approval.auto_rejected = True
        approval.reference_action_at = timezone.now()
        approval.save()

        volunteer = approval.volunteer
        volunteer.status = Volunteer.Status.AUTO_REJECTED
        volunteer.save()

        AuditLog.objects.create(volunteer=volunteer, action="auto_rejected",
                                 detail="Volunteer did not approve within 24 hours.")

        for admin in User.objects.filter(is_staff=True):
            notify(admin, "Application Auto-Rejected",
                   f"{volunteer.name}'s reference did not respond within 24 hours.",
                   Notification.Type.STATUS_UPDATE, related_volunteer=volunteer)

        push_status_update(volunteer.id, {"volunteer_id": volunteer.id, "status": volunteer.status})