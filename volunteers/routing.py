# backend/volunteers/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/volunteers/notifications/$", consumers.NotificationConsumer.as_asgi()),
]