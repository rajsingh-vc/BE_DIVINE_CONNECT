import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

from volunteers.routing import websocket_urlpatterns
from volunteers.ws_auth import JWTAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # Swapped AuthMiddlewareStack -> JWTAuthMiddleware: the frontend sends
    # the JWT as a ?token= query param, not a session cookie, so
    # AuthMiddlewareStack always resolved scope["user"] to AnonymousUser
    # and every WS handshake got rejected.
    "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
})