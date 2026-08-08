"""
Sends a notification to every Volunteer and Devotee whenever an admin
adds, updates, or deletes a prasad inventory item.

This does NOT touch InventoryItemViewSet, IsAdminOrReadOnly, or any
existing inventory logic — permissions stay exactly as they are
(admin: add/update/delete, volunteer/devotee: view only). This file
just listens for InventoryItem save/delete events (which already only
admins can trigger, thanks to IsAdminOrReadOnly) and fans out a
notification using the existing volunteers.Notification model +
notify() helper (same one already used for volunteer approvals), so no
new tables, no new push mechanism — it reuses what's already wired up.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import InventoryItem

User = get_user_model()


def _notify_volunteers_and_devotees(title, message):
    # Imported lazily (inside the function) instead of at module level so
    # this file has no import-time dependency on the volunteers app's
    # load order — it only needs volunteers to be ready by the time an
    # InventoryItem is actually saved/deleted, which it always will be.
    from volunteers.models import Notification
    from volunteers.notifications import notify

    recipients = User.objects.filter(
        user_type__in=[User.UserType.VOLUNTEER, User.UserType.DEVOTEE]
    )
    for user in recipients:
        notify(
            user,
            title,
            message,
            Notification.Type.ANNOUNCEMENT_IMPORTANT,
        )


@receiver(post_save, sender=InventoryItem)
def notify_on_inventory_save(sender, instance, created, **kwargs):
    if created:
        title = "New Prasad Item Added"
        message = (
            f"{instance.item_name} ({instance.sku}) has been added to inventory. "
            f"Stock: {instance.stock} {instance.unit}."
        )
    else:
        title = "Prasad Inventory Updated"
        message = (
            f"{instance.item_name} ({instance.sku}) was updated. "
            f"Stock: {instance.stock} {instance.unit}."
        )
    _notify_volunteers_and_devotees(title, message)


@receiver(post_delete, sender=InventoryItem)
def notify_on_inventory_delete(sender, instance, **kwargs):
    title = "Prasad Inventory Item Removed"
    message = f"{instance.item_name} ({instance.sku}) has been removed from inventory."
    _notify_volunteers_and_devotees(title, message)