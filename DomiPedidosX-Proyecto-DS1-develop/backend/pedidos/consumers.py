"""WebSockets del tablero de cocina (HU-29), autenticados con JWT."""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from django.contrib.auth import get_user_model

from usuarios.roles import ADMINISTRADOR, COCINA, OPERADOR, obtener_rol, obtener_sede


@database_sync_to_async
def usuario_desde_token(token):
    """Valida el access token y recupera un usuario activo."""
    try:
        datos = AccessToken(token)
        usuario_id = datos.get("user_id")
        if not usuario_id:
            return None
        return get_user_model().objects.filter(pk=usuario_id, is_active=True).first()
    except (InvalidToken, TokenError, TypeError, ValueError):
        return None


@database_sync_to_async
def datos_acceso_cocina(usuario):
    """Devuelve (rol, sede_id) si el usuario puede escuchar el tablero."""
    rol = obtener_rol(usuario)
    if rol not in (COCINA, OPERADOR, ADMINISTRADOR):
        return None, None
    sede = obtener_sede(usuario)
    if rol != ADMINISTRADOR and sede is None:
        return None, None
    return rol, sede.pk if sede else None


class TableroCocinaConsumer(AsyncJsonWebsocketConsumer):
    """Notifica cambios de pedidos de una sede sin exponer datos del cliente."""

    async def connect(self):
        parametros = parse_qs(self.scope.get("query_string", b"").decode())
        token = parametros.get("token", [""])[0]
        usuario = await usuario_desde_token(token) if token else None
        if usuario is None:
            await self.close(code=4401)
            return

        rol, sede_id = await datos_acceso_cocina(usuario)
        if rol is None:
            await self.close(code=4403)
            return

        # El administrador escucha todas las sedes; cocina y operador solo la propia.
        self.grupo = "cocina_todas_sedes" if rol == ADMINISTRADOR else f"cocina_sede_{sede_id}"
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()
        await self.send_json({"tipo": "conexion.establecida"})

    async def disconnect(self, close_code):
        grupo = getattr(self, "grupo", None)
        if grupo:
            await self.channel_layer.group_discard(grupo, self.channel_name)

    async def pedido_actualizado(self, event):
        """Entrega un aviso mínimo; el frontend vuelve a consultar el tablero."""
        await self.send_json(
            {
                "tipo": "pedido.actualizado",
                "pedido_id": event["pedido_id"],
                "sede_id": event["sede_id"],
                "estado": event["estado"],
                "estado_anterior": event["estado_anterior"],
            }
        )
