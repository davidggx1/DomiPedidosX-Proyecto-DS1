import uuid
from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError

from usuarios.models import Cliente, DireccionEntrega
from . import capacidad
from .correos import enviar_correo_confirmacion
from .models import (
    ConsumoCupoCombo,
    Pedido,
    DetallePedido,
    DetallePedidoAdicion,
    DetallePedidoExclusion,
    Factura,
    EstadoPedido,
    HistorialEstadoPedido,
    OrigenPedido,
    EstadoFactura,
)
from .stock import descontar_stock


def crear_pedido_operador(usuario_operador, datos):
    # Lazy import: servicios -> eventos -> consumers -> views -> this module.
    from .servicios import ErrorConfirmacion, _preparar_carrito

    empleado = getattr(usuario_operador, "empleado", None)
    if not empleado or not empleado.sede:
        raise ValidationError({"detail": "El operador no tiene una sede asignada."})

    sede = empleado.sede
    origen = datos["origen"]
    cliente_id = datos.get("cliente_id")
    direccion_id = datos.get("direccion_id")

    cliente = None
    if cliente_id:
        try:
            cliente = Cliente.objects.get(pk=cliente_id)
        except Cliente.DoesNotExist:
            raise ValidationError({"cliente_id": "El cliente especificado no existe."})

    direccion = None
    costo_domicilio = Decimal("0.00")

    if origen == OrigenPedido.TELEFONICO:
        try:
            direccion = DireccionEntrega.objects.get(pk=direccion_id)
        except DireccionEntrega.DoesNotExist:
            raise ValidationError({"direccion_id": "La dirección especificada no existe."})

        # Tarifa plana para domicilios vía telefónica
        costo_domicilio = Decimal("4000.00")

    with transaction.atomic():
        # HU-61: same rule as the web, the operator can confirm without a slot
        capacidad.validar_cupo_nuevo_pedido(
            sede,
            puede_confirmar_manual=True,
            confirmado_sin_franja=datos.get("confirmar_sin_franja", False),
        )

        numero_pedido = f"PED-{uuid.uuid4().hex[:8].upper()}"

        pedido = Pedido.objects.create(
            numero_pedido=numero_pedido,
            sede=sede,
            cliente=cliente,
            empleado=empleado,
            origen=origen,
            estado=EstadoPedido.RECIBIDO,  # Los pedidos de operador entran como 'recibido'
            descripcion=datos.get("observaciones", ""),
        )

        if direccion:
            pedido.asignar_direccion_entrega(direccion)
            pedido.save()

        # Same catalogue, price and stock rules as the web checkout: sizes add
        # precio_adicional, line subtotals include add-ons and stock is locked,
        # validated and decremented (so cancelling can restore it later).
        lineas, consumos, errores, stock = _preparar_carrito(datos["items"], sede)
        if errores:
            raise ErrorConfirmacion("Algunos ítems no se pueden confirmar.", errores)

        for l in lineas:
            detalle = DetallePedido.objects.create(
                pedido=pedido,
                producto=l["producto"],
                combo=l["combo"],
                producto_tamano=l["tamano"],
                cantidad=l["cantidad"],
                precio_unitario=l["precio_unitario"],
                subtotal=l["subtotal"],
                observaciones=l["observaciones"],
            )
            DetallePedidoAdicion.objects.bulk_create([
                DetallePedidoAdicion(
                    detalle_pedido=detalle, adicion=a, cantidad=c, precio_unitario=a.precio
                )
                for a, c in l["adiciones"]
            ])
            DetallePedidoExclusion.objects.bulk_create([
                DetallePedidoExclusion(
                    detalle_pedido=detalle, insumo=i, nombre_insumo=i.nombre
                )
                for i in l["exclusiones"]
            ])

        for cs, cantidad in consumos:
            ConsumoCupoCombo.objects.create(combo_sede=cs, pedido=pedido, cantidad_usada=cantidad)

        descontar_stock(**stock)

        HistorialEstadoPedido.objects.create(
            pedido=pedido,
            usuario=usuario_operador,
            estado=EstadoPedido.RECIBIDO,
            observacion="Pedido creado por el operador.",
        )

        subtotal_pedido = sum((l["subtotal"] for l in lineas), Decimal("0.00"))
        iva = Decimal("0.00")
        total = subtotal_pedido + costo_domicilio

        factura = Factura.objects.create(
            pedido=pedido,
            numero=f"FAC-{uuid.uuid4().hex[:8].upper()}",
            subtotal=subtotal_pedido,
            iva=iva,
            costo_domicilio=costo_domicilio,
            valor_descuento=Decimal("0.00"),
            total=total,
            metodo_pago=datos["metodo_pago"],
            estado_factura=EstadoFactura.PAGADA if origen == OrigenPedido.MOSTRADOR else EstadoFactura.PENDIENTE,
        )

        # HU-50: si el pedido tiene cliente con correo, recibe la confirmación.
        transaction.on_commit(lambda: enviar_correo_confirmacion(pedido))

        return pedido, factura