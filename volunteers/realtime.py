from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def push_notification(user_id, payload):
    """Push a real-time event to a user's notification group.
    Requires channels + a consumer that subscribes each user to group `user_{id}`."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {"type": "notification.message", "payload": payload},
    )


def push_status_update(volunteer_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"volunteer_{volunteer_id}",
        {"type": "status.update", "payload": payload},
    )