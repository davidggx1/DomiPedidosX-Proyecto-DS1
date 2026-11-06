import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from pedidos.models import Pedido
from pedidos.views import pedidos_visibles, rol_de


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
