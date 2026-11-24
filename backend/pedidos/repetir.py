"""
HU-26 · Repetir un pedido anterior.

POST /api/pedidos/mios/<id>/repetir/   (solo el cliente dueño del pedido)

No crea nada: arma las líneas del carrito con lo que tenía el pedido (producto,
tamaño, adiciones, ingredientes quitados y cantidad, o el combo) y las valida
contra el menú de HOY en la misma sede, con las mismas reglas del carrito (HU-21):
- precio actual, no el que se pagó entonces;
- lo que ya no se puede pedir (producto inactivo, agotado, adición retirada,
  combo vencido o sin cupo...) no entra y vuelve en `no_disponibles` con el motivo.

El frontend pone `lineas` en el carrito y el cliente revisa y paga como siempre;
el checkout vuelve a validar todo al crear el pedido.

Respuesta:
    {"sede": {"id", "nombre"}, "lineas": [...], "no_disponibles": [{"nombre", "motivo"}]}
Cada línea tiene la forma que usa el carrito del frontend (utils/carrito.js).
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from menu.carrito import LineaCarritoSerializer, calcular_precio_unitario
from menu.models import ProductoInsumo
from promociones import combos as reglas_combos, cupos as reglas_cupos
from promociones.models import ComboSede
from usuarios.permissions import EsCliente

from .estados import CLIENTE
from .serializers import nombre_linea
from .views import pedidos_visibles


def _primer_error(errores):
    """Primer mensaje legible de un ValidationError de DRF."""
    if isinstance(errores, dict):
        for valor in errores.values():
            return _primer_error(valor)
    if isinstance(errores, list) and errores:
        return _primer_error(errores[0])
    return str(errores)


def _imagen(producto, request):
    if producto.imagen:
        return request.build_absolute_uri(producto.imagen.url)
    return producto.imagen_url or None


def _linea_producto(detalle, sede, request):
    """(línea para el carrito, None) o (None, motivo)."""
    producto = detalle.producto
    exclusiones = list(
        ProductoInsumo.objects.filter(
            producto=producto, insumo_id__in=[e.insumo_id for e in detalle.exclusiones.all()]
        ).values_list("id", flat=True)
    )
    datos = {
        "producto": producto.pk,
        "tamano": detalle.producto_tamano_id,
        "adiciones": [{"adicion": a.adicion_id, "cantidad": a.cantidad} for a in detalle.adiciones.all()],
        "exclusiones": exclusiones,
        "cantidad": detalle.cantidad,
    }
    serializer = LineaCarritoSerializer(data=datos, context={"sede": sede})
    if not serializer.is_valid():
        return None, _primer_error(serializer.errors)

    validado = serializer.validated_data
    tamano = validado["tamano"]
    return {
        "producto": {
            "id": producto.pk,
            "nombre": producto.nombre,
            "imagen": _imagen(producto, request),
            "precio_base": str(producto.precio_base),
        },
        "tamano": tamano and {
            "id": tamano.pk,
            "nombre": tamano.nombre,
            "precio_adicional": str(tamano.precio_adicional),
        },
        "adiciones": [
            {"adicion": adicion.pk, "nombre": adicion.nombre, "precio": str(adicion.precio), "cantidad": cantidad}
            for adicion, cantidad in validado["adiciones"]
        ],
        "exclusiones": [{"id": ing.pk, "nombre": ing.insumo.nombre} for ing in validado["exclusiones"]],
        "cantidad": detalle.cantidad,
        "precio_unitario": str(calcular_precio_unitario(producto, tamano, validado["adiciones"])),
    }, None


def _linea_combo(detalle, sede):
    """Mismas reglas que el combo en el menú (HU-85): vigente, en la sede, productos y cupo."""
    combo = detalle.combo
    combo_sede = ComboSede.objects.filter(combo=combo, sede=sede).first()
    if combo_sede is None:
        return None, "El combo ya no se ofrece en esta sede."
    productos = reglas_combos.detalle_productos(combo, sede)
    disponible, motivo = reglas_combos.disponibilidad(combo, combo_sede, productos)
    if not disponible:
        return None, motivo
    restante = reglas_cupos.cupo_restante(combo_sede)
    if restante is not None and detalle.cantidad > restante:
        return None, f"Solo quedan {restante} unidades disponibles hoy."
    return {
        "combo": {
            "id": combo.pk,
            "nombre": combo.nombre,
            "descripcion": combo.descripcion,
            "productos_incluidos": [
                {"producto_id": p["producto"], "nombre": p["nombre"], "cantidad": p["cantidad"]} for p in productos
            ],
        },
        "cantidad": detalle.cantidad,
        "precio_unitario": str(combo.precio),
    }, None


class NoDisponibleSerializer(serializers.Serializer):
    nombre = serializers.CharField()
    motivo = serializers.CharField()


class SedeRepetirSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class RepetirPedidoSerializer(serializers.Serializer):
    sede = SedeRepetirSerializer()
    lineas = serializers.ListField(
        child=serializers.DictField(), help_text="Líneas listas para el carrito, con el precio de hoy."
    )
    no_disponibles = NoDisponibleSerializer(many=True)


class RepetirPedidoView(APIView):
    permission_classes = [EsCliente]

    @extend_schema(
        tags=["Pedidos"],
        summary="Repetir un pedido anterior (HU-26)",
        description=(
            "Arma las líneas del carrito con los productos y combos del pedido, validadas con el menú "
            "y los precios de hoy en la misma sede. No crea ningún pedido."
        ),
        request=None,
        responses={
            200: RepetirPedidoSerializer,
            404: OpenApiResponse(description="El pedido no existe o no es del cliente."),
            409: OpenApiResponse(description="La sede del pedido ya no está activa."),
        },
    )
    def post(self, request, pk):
        pedido = get_object_or_404(
            pedidos_visibles(request.user, CLIENTE).select_related("sede"), pk=pk
        )
        sede = pedido.sede
        if not sede.activa:
            return Response(
                {"detail": f"{sede.nombre} ya no está recibiendo pedidos."}, status=status.HTTP_409_CONFLICT
            )

        detalles = pedido.detalles.select_related("producto", "combo", "producto_tamano").prefetch_related(
            "adiciones", "exclusiones"
        )
        lineas, no_disponibles = [], []
        for detalle in detalles.order_by("id"):
            if detalle.combo_id:
                linea, motivo = _linea_combo(detalle, sede)
            elif detalle.producto_id:
                linea, motivo = _linea_producto(detalle, sede, request)
            else:
                continue
            if linea:
                lineas.append(linea)
            else:
                no_disponibles.append({"nombre": nombre_linea(detalle), "motivo": motivo})

        return Response({"sede": {"id": sede.pk, "nombre": sede.nombre}, "lineas": lineas, "no_disponibles": no_disponibles})
