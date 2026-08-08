from django.db.models.signals import post_save
from django.dispatch import receiver

from devotees.models import Devotee


@receiver(post_save, sender=Devotee)
def issue_qr_code_for_new_devotee(sender, instance, created, **kwargs):
    """The moment a Devotee row is created -- self-signup, front-desk
    registration, or a walk-in record with no login at all -- issue a QR
    record using their existing `devotee_code`. This covers every devotee,
    not just ones with a User login, since `Devotee.user` is nullable.
    """
    if not created:
        return

    from .models import DevoteeQRStatus

    DevoteeQRStatus.get_or_create_for_devotee(instance)