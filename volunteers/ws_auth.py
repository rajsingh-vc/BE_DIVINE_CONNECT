from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token):
    try:
        validated = AccessToken(token)
        return User.objects.get(id=validated["user_id"])
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Resolves scope["user"] from a ?token=<jwt> query param on the WS URL.

    AuthMiddlewareStack only understands session cookies, which the
    frontend never sends on a WebSocket connection — so it always resolved
    to AnonymousUser and NotificationConsumer.connect() rejected every
    handshake. This replaces it for the websocket protocol only.
    """

    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope.get("query_string", b"").decode())
        token = query_string.get("token", [None])[0]
        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)