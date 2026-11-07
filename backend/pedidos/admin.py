from django.contrib import admin

from .models import Pedido, DetallePedido, DetallePedidoAdicion, DetallePedidoExclusion, HistorialEstadoPedido, Factura, ConsumoCupoCombo, Notificacion

admin.site.register(Pedido)
admin.site.register(DetallePedido)
admin.site.register(DetallePedidoAdicion)
admin.site.register(HistorialEstadoPedido)
admin.site.register(Factura)
admin.site.register(ConsumoCupoCombo)
admin.site.register(Notificacion)
admin.site.register(DetallePedidoExclusion)