import uuid
from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError

from menu.models import Producto, ProductoTamano, Adicion, Insumo
from usuarios.models import Cliente, DireccionEntrega
from .models import (
    Pedido,
    DetallePedido,
    DetallePedidoAdicion,
    DetallePedidoExclusion,
    Factura,
    EstadoPedido,
    OrigenPedido,
    EstadoFactura,
)


def crear_pedido_operador(usuario_operador, datos):
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

        subtotal_pedido = Decimal("0.00")

        for item in datos["items"]:
            producto_id = item.get("producto_id")
            tamano_id = item.get("tamano_id")
            cantidad = item["cantidad"]
            obs_item = item.get("observaciones", "")

            producto = Producto.objects.get(pk=producto_id)
            tamano = ProductoTamano.objects.get(pk=tamano_id) if tamano_id else None

            precio_base = tamano.precio if tamano else producto.precio_base
            subtotal_linea = precio_base * cantidad

            detalle = DetallePedido.objects.create(
                pedido=pedido,
                producto=producto,
                producto_tamano=tamano,
                cantidad=cantidad,
                precio_unitario=precio_base,
                subtotal=subtotal_linea,
                observaciones=obs_item,
            )

            # Procesar adiciones
            for ad_item in item.get("adiciones", []):
                adicion = Adicion.objects.get(pk=ad_item["adicion_id"])
                cant_ad = ad_item.get("cantidad", 1)
                precio_ad = adicion.precio * cant_ad
                DetallePedidoAdicion.objects.create(
                    detalle_pedido=detalle,
                    adicion=adicion,
                    cantidad=cant_ad,
                    precio_unitario=adicion.precio,
                )
                subtotal_linea += precio_ad

            # Procesar exclusiones ("sin")
            for insumo_id in item.get("exclusiones", []):
                insumo = Insumo.objects.get(pk=insumo_id)
                DetallePedidoExclusion.objects.create(
                    detalle_pedido=detalle,
                    insumo=insumo,
                    nombre_insumo=insumo.nombre,
                )

            subtotal_pedido += subtotal_linea

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

        return pedido, factura