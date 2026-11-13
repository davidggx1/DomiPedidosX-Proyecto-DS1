"""
HU-70 · Panel de indicadores del día (administrador).

GET /api/pedidos/indicadores/            Consolidado de todas las sedes activas.
GET /api/pedidos/indicadores/?sede=<id>  Una sola sede (criterio 2).

Indicadores de los pedidos creados hoy (día local, igual que la HU-67):
- pedidos: cuántos se crearon. Coincide con el total de "Pedidos del día" (criterio 4 de la HU-67).
- ventas: suma de las facturas, SIN contar los cancelados (criterio 3).
- cancelaciones: cuántos se cancelaron.
- tiempo promedio de entrega: minutos entre la creación y la entrega, de los ya entregados.
- ocupación de cocina por sede: pedidos que ocupan cupo frente al máximo de la franja actual (HU-61).

Un día sin pedidos devuelve todo en 0, sin errores (criterio 4).
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from sedes.models import Sede
from usuarios.permissions import rol_requerido
from usuarios.roles import ADMINISTRADOR

from .capacidad import estado_capacidad
from .models import EstadoPedido, HistorialEstadoPedido, Pedido
from .resumen import rango_del_dia


def _promedio(minutos):
    return round(sum(minutos) / len(minutos)) if minutos else 0


def _ocupacion(sede, ahora):
    estado = estado_capacidad(sede, puede_confirmar_manual=True, ahora=ahora)
    return {
        "activos": estado["activos"],
        "maximo": estado["maximo"],
        "porcentaje": estado["porcentaje"],
        "estado": estado["estado"],
    }


def indicadores_del_dia(sedes, fecha, ahora=None):
    """Indicadores de `fecha` para cada sede de `sedes` y el consolidado."""
    ahora = ahora or timezone.now()
    inicio, fin = rango_del_dia(fecha)
    del_dia = Pedido.objects.filter(sede__in=sedes, fecha_creacion__gte=inicio, fecha_creacion__lt=fin)
    cancelado = Q(estado=EstadoPedido.CANCELADO)

    conteos = {
        fila["sede_id"]: fila
        for fila in del_dia.values("sede_id").annotate(
            pedidos=Count("id"),
            cancelaciones=Count("id", filter=cancelado),
            ventas=Sum("factura__total", filter=~cancelado),
        )
    }

    # Minutos de creación a entrega de cada pedido de hoy ya entregado
    entregas = defaultdict(list)
    for paso in HistorialEstadoPedido.objects.filter(
        pedido__in=del_dia, estado=EstadoPedido.ENTREGADO
    ).values("pedido__sede_id", "pedido__fecha_creacion", "fecha_hora"):
        minutos = (paso["fecha_hora"] - paso["pedido__fecha_creacion"]).total_seconds() / 60
        entregas[paso["pedido__sede_id"]].append(minutos)

    por_sede = []
    for sede in sedes:
        fila = conteos.get(sede.pk, {})
        por_sede.append({
            "sede_id": sede.pk,
            "nombre": sede.nombre,
            "pedidos": fila.get("pedidos", 0),
            "ventas": fila.get("ventas") or Decimal("0"),
            "cancelaciones": fila.get("cancelaciones", 0),
            "entregados": len(entregas[sede.pk]),
            "tiempo_promedio_entrega": _promedio(entregas[sede.pk]),
            "ocupacion": _ocupacion(sede, ahora),
        })

    todos_los_tiempos = [m for sede in sedes for m in entregas[sede.pk]]
    return {
        "fecha": fecha,
        "pedidos": sum(s["pedidos"] for s in por_sede),
        "ventas": sum((s["ventas"] for s in por_sede), Decimal("0")),
        "cancelaciones": sum(s["cancelaciones"] for s in por_sede),
        "entregados": len(todos_los_tiempos),
        "tiempo_promedio_entrega": _promedio(todos_los_tiempos),
        "sedes": por_sede,
    }


# --- Documentación de la respuesta (SCRUM-120) ------------------------------------


class OcupacionSerializer(serializers.Serializer):
    activos = serializers.IntegerField(help_text="Pedidos que ocupan cupo en cocina ahora.")
    maximo = serializers.IntegerField(allow_null=True, help_text="Cupo de la franja actual; null sin franja.")
    porcentaje = serializers.IntegerField(allow_null=True)
    estado = serializers.ChoiceField(choices=["disponible", "saturada", "sin_franja"])


class IndicadoresSedeSerializer(serializers.Serializer):
    sede_id = serializers.IntegerField()
    nombre = serializers.CharField()
    pedidos = serializers.IntegerField()
    ventas = serializers.DecimalField(max_digits=14, decimal_places=2)
    cancelaciones = serializers.IntegerField()
    entregados = serializers.IntegerField()
    tiempo_promedio_entrega = serializers.IntegerField(help_text="Minutos; 0 si aún no hay entregas.")
    ocupacion = OcupacionSerializer()


class IndicadoresDiaSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    pedidos = serializers.IntegerField()
    ventas = serializers.DecimalField(max_digits=14, decimal_places=2, help_text="Sin los pedidos cancelados.")
    cancelaciones = serializers.IntegerField()
    entregados = serializers.IntegerField()
    tiempo_promedio_entrega = serializers.IntegerField(help_text="Minutos; 0 si aún no hay entregas.")
    sedes = IndicadoresSedeSerializer(many=True)


class IndicadoresDiaView(APIView):
    permission_classes = [rol_requerido(ADMINISTRADOR)]

    @extend_schema(
        tags=["Pedidos"],
        summary="Indicadores del día (HU-70)",
        description=(
            "Pedidos, ventas (sin cancelados), cancelaciones, tiempo promedio de entrega y ocupación "
            "de cocina de hoy. Sin `sede`: consolidado de las sedes activas. Solo administrador."
        ),
        parameters=[OpenApiParameter("sede", int, description="Ver una sola sede.")],
        responses={
            200: IndicadoresDiaSerializer,
            400: OpenApiResponse(description="`sede` no es un número."),
            403: OpenApiResponse(description="No es administrador."),
            404: OpenApiResponse(description="La sede no existe."),
        },
    )
    def get(self, request):
        sede = request.query_params.get("sede")
        if sede is None or sede == "":
            sedes = list(Sede.objects.filter(activa=True).order_by("nombre"))
        elif not sede.isdigit():
            return Response({"sede": "Debe ser el id numérico de una sede."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            sedes = list(Sede.objects.filter(pk=int(sede)))
            if not sedes:
                return Response({"detail": "La sede no existe."}, status=status.HTTP_404_NOT_FOUND)

        datos = indicadores_del_dia(sedes, timezone.localdate())
        return Response(IndicadoresDiaSerializer(datos).data)
