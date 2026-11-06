import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from pedidos.models import Pedido
from usuarios.models import Repartidor
from pedidos.views import pedidos_visibles, rol_de
from usuarios.roles import ADMINISTRADOR, OPERADOR, REPARTIDOR, obtener_rol, obtener_sede

class EstadoPedidoConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close(code=4401)
            return

        self.pedido_id = self.scope['url_route']['kwargs']['pedido_id']
        if not await self.puede_ver_pedido():
            await self.close(code=4403)
            return

        self.group_name = f'pedido_{self.pedido_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def puede_ver_pedido(self):
        rol = rol_de(self.scope['user'])
        return bool(rol and pedidos_visibles(self.scope['user'], rol).filter(pk=self.pedido_id).exists())

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def estado_pedido_cambiado(self, event):
        await self.send(text_data=json.dumps(event['payload']))


GRUPO_ADMIN = "pedidos_admin"


def grupo_sede(sede_id):
    return f"pedidos_sede_{sede_id}"


class PedidosEntrantesConsumer(AsyncJsonWebsocketConsumer):
    """Panel del operador: recibe los pedidos de SU sede. El administrador recibe todos."""

    async def connect(self):
        usuario = self.scope["user"]
        if not usuario.is_authenticated:
            await self.close(code=4401)
            return

        rol, sede_id = await self._rol_y_sede(usuario)
        if rol == ADMINISTRADOR:
            self.grupo = GRUPO_ADMIN
        elif rol == OPERADOR and sede_id is not None:
            self.grupo = grupo_sede(sede_id)
        else:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        grupo = getattr(self, "grupo", None)
        if grupo:
            await self.channel_layer.group_discard(grupo, self.channel_name)

    async def pedido_evento(self, event):
        await self.send_json(event["data"])

    @database_sync_to_async
    def _rol_y_sede(self, usuario):
        sede = obtener_sede(usuario)
        return obtener_rol(usuario), (sede.pk if sede else None)


def grupo_repartidor(repartidor_id):
    return f"entregas_repartidor_{repartidor_id}"


class MisEntregasConsumer(AsyncJsonWebsocketConsumer):
    """
    App del repartidor (HU-42): avisa cuando su lista de entregas cambia
    (le asignan o le retiran un pedido, o uno de sus pedidos cambia de estado).
    El aviso solo trae el id del pedido; la app vuelve a pedir la lista.
    """

    async def connect(self):
        usuario = self.scope["user"]
        if not usuario.is_authenticated:
            await self.close(code=4401)
            return

        repartidor_id = await self._repartidor_id(usuario)
        if repartidor_id is None:
            await self.close(code=4403)
            return

        self.grupo = grupo_repartidor(repartidor_id)
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        grupo = getattr(self, "grupo", None)
        if grupo:
            await self.channel_layer.group_discard(grupo, self.channel_name)

    async def entregas_evento(self, event):
        await self.send_json(event["data"])

    @database_sync_to_async
    def _repartidor_id(self, usuario):
        if obtener_rol(usuario) != REPARTIDOR:
            return None
        return Repartidor.objects.filter(empleado__usuario=usuario).values_list("pk", flat=True).first()
