"""
HU-46 · Historial de entregas del repartidor.

GET /api/pedidos/mis-entregas/historial/?desde=AAAA-MM-DD&hasta=AAAA-MM-DD

- Solo los pedidos que ESTE repartidor entregó (estado "Entregado"), según el día
  local en que se marcaron como entregados (no el día en que se crearon).
- Sin fechas: hoy. Con fechas: del día `desde` al día `hasta`, los dos incluidos
  (mismas reglas que los reportes: pedidos/rango_fechas.py).
- Detalle del dinero (HU-45): por cada entrega, el total, el método de pago y, si
  fue en efectivo, cuánto recibió y el cambio. El resumen suma lo cobrado en
  efectivo (lo que el repartidor debe entregar en la sede) y lo pagado en línea.
"""
from decimal import Decimal

from django.db.models import OuterRef, Subquery
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permissions import EsRepartidor
from usuarios.roles import REPARTIDOR

from .models import EstadoPedido, HistorialEstadoPedido, MetodoPago
from .rango_fechas import RangoFechasInvalido, leer_rango_fechas
from .views import pedidos_visibles

CERO = Decimal("0.00")


def entregas_en_rango(usuario, inicio, fin):
    entregado_en = (
        HistorialEstadoPedido.objects.filter(pedido=OuterRef("pk"), estado=EstadoPedido.ENTREGADO)
        .order_by("fecha_hora")
        .values("fecha_hora")[:1]
    )
    return (
        pedidos_visibles(usuario, REPARTIDOR)
        .filter(estado=EstadoPedido.ENTREGADO)
        .annotate(entregado_en=Subquery(entregado_en))
        .filter(entregado_en__gte=inicio, entregado_en__lt=fin)
        .select_related("cliente", "factura")
        .order_by("-entregado_en", "-id")
    )


def _fila(pedido):
    factura = getattr(pedido, "factura", None)
    total = factura.total if factura else None
    efectivo = bool(factura and factura.metodo_pago == MetodoPago.EFECTIVO)
    recibido = factura.monto_recaudado if efectivo else None
    return {
        "id": pedido.pk,
        "numero_pedido": pedido.numero_pedido,
        "entregado_en": pedido.entregado_en,
        "cliente": f"{pedido.cliente.nombres} {pedido.cliente.apellidos}" if pedido.cliente else None,
        "entrega_direccion": pedido.entrega_direccion,
        "entrega_barrio": pedido.entrega_barrio,
        "total": total,
        "metodo_pago": factura.metodo_pago if factura else None,
        "metodo_pago_nombre": factura.get_metodo_pago_display() if factura else None,
        "monto_recaudado": recibido,
        "cambio": recibido - total if recibido is not None and total is not None else None,
    }


def _resumen(filas):
    en_efectivo = [f for f in filas if f["metodo_pago"] == MetodoPago.EFECTIVO]
    en_linea = [f for f in filas if f["metodo_pago"] and f["metodo_pago"] != MetodoPago.EFECTIVO]
    return {
        "entregas": len(filas),
        "pedidos_efectivo": len(en_efectivo),
        "efectivo_cobrado": sum((f["total"] for f in en_efectivo), CERO),
        "cambio_entregado": sum((f["cambio"] or CERO for f in en_efectivo), CERO),
        "pedidos_en_linea": len(en_linea),
        "pagado_en_linea": sum((f["total"] for f in en_linea), CERO),
    }


# --- Respuesta documentada ----------------------------------------------------------


class EntregaHistorialSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero_pedido = serializers.CharField()
    entregado_en = serializers.DateTimeField()
    cliente = serializers.CharField(allow_null=True)
    entrega_direccion = serializers.CharField()
    entrega_barrio = serializers.CharField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    metodo_pago = serializers.CharField(allow_null=True)
    metodo_pago_nombre = serializers.CharField(allow_null=True)
    monto_recaudado = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True, help_text="Solo en efectivo: lo que entregó el cliente."
    )
    cambio = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


class ResumenEntregasSerializer(serializers.Serializer):
    entregas = serializers.IntegerField()
    pedidos_efectivo = serializers.IntegerField()
    efectivo_cobrado = serializers.DecimalField(
        max_digits=14, decimal_places=2, help_text="Total de los pedidos en efectivo: lo que se entrega en la sede."
    )
    cambio_entregado = serializers.DecimalField(max_digits=14, decimal_places=2)
    pedidos_en_linea = serializers.IntegerField()
    pagado_en_linea = serializers.DecimalField(max_digits=14, decimal_places=2)


class HistorialEntregasSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()
    resumen = ResumenEntregasSerializer()
    entregas = EntregaHistorialSerializer(many=True)


class HistorialEntregasView(APIView):
    permission_classes = [EsRepartidor]

    @extend_schema(
        tags=["Entregas"],
        summary="Historial de entregas del repartidor (HU-46)",
        description="Pedidos entregados por el repartidor en el rango (por defecto hoy) y el dinero cobrado.",
        parameters=[
            OpenApiParameter("desde", str, description="AAAA-MM-DD (por defecto hoy)"),
            OpenApiParameter("hasta", str, description="AAAA-MM-DD (por defecto hoy)"),
        ],
        responses={
            200: HistorialEntregasSerializer,
            400: OpenApiResponse(description="Fechas mal escritas o inicio posterior al fin."),
        },
    )
    def get(self, request):
        parametros = request.query_params
        if not parametros.get("desde") and not parametros.get("hasta"):
            hoy = timezone.localdate().isoformat()
            parametros = {"desde": hoy, "hasta": hoy}
        try:
            desde, hasta, inicio, fin = leer_rango_fechas(parametros)
        except RangoFechasInvalido as error:
            return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)

        filas = [_fila(pedido) for pedido in entregas_en_rango(request.user, inicio, fin)]
        datos = {"desde": desde, "hasta": hasta, "resumen": _resumen(filas), "entregas": filas}
        return Response(HistorialEntregasSerializer(datos).data)
