from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _usuario_desde_token(token):
    try:
        user_id = AccessToken(token)["user_id"]
    except (TokenError, KeyError):
        return AnonymousUser()
    usuario = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    return usuario or AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """El navegador no puede enviar headers en un WebSocket: el JWT viaja en ?token=..."""

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = query.get("token", [None])[0]
        scope["user"] = await _usuario_desde_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)