"""
HU-74 · Patrones de demanda (administrador).

GET /api/pedidos/reportes/demanda/?desde=AAAA-MM-DD&hasta=AAAA-MM-DD&sede=<id>

Criterio (Jira SCRUM-164): mapas de calor y gráficos del volumen de ventas por día de
la semana y por hora, para ver las horas pico.

Pedidos válidos: los mismos del reporte de ventas (HU-71) y del panel del día (HU-70),
es decir, no cancelados y con factura, creados en el rango (días locales, los dos
incluidos; sin fechas, los últimos 7 días). Así las cifras coinciden entre reportes.

El día y la hora salen de `fecha_creacion` en la hora local (America/Bogota): con
USE_TZ=True, ExtractIsoWeekDay y ExtractHour convierten a la zona horaria actual.
Días ISO: 1 = lunes ... 7 = domingo.

Respuesta:
- `celdas`: la cuadrícula completa de 7 días × 24 horas (pedidos y ventas de cada una),
  para pintar el mapa de calor sin huecos. Cada celda trae también `fechas`: los días
  (AAAA-MM-DD, hora local) que aportaron pedidos, porque una celda suma todos los
  viernes del rango y así se puede saber de qué viernes salió cada número.
- `por_dia` y `por_hora`: los totales de cada fila y columna, para los gráficos.
- `dia_pico` y `hora_pico`: los de más pedidos (empate: más ventas; luego el primero).
Inicio posterior al fin -> 400. Sin pedidos en el rango, `sin_datos` es true.
"""
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, TruncDate
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from sedes.models import Sede
from usuarios.permissions import rol_requerido
from usuarios.roles import ADMINISTRADOR

from .models import Factura
from .rango_fechas import RangoFechasInvalido, leer_rango_fechas
from .reportes_ventas import _validos  # misma regla de "pedido válido" que HU-70/71

CERO = Decimal("0")
DIAS = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"}
HORAS = range(24)


def _dinero(valor):
    return (valor or CERO).quantize(Decimal("0.01"))


def _pico(filas):
    """Fila con más pedidos (empate: más ventas; si sigue el empate, la primera). None sin pedidos."""
    candidatas = [f for f in filas if f["pedidos"] > 0]
    if not candidatas:
        return None
    return max(candidatas, key=lambda f: (f["pedidos"], f["ventas"]))


def patrones_demanda(inicio, fin, sede=None):
    facturas = Factura.objects.filter(_validos(inicio, fin, sede))
    filas = (
        facturas.annotate(dia=ExtractIsoWeekDay("pedido__fecha_creacion"), hora=ExtractHour("pedido__fecha_creacion"))
        .values("dia", "hora")
        .annotate(pedidos=Count("pk"), ventas=Sum("total"))
    )
    por_celda = {(f["dia"], f["hora"]): f for f in filas}

    # Fechas distintas de cada celda (TruncDate también usa la hora local)
    fechas_por_celda = {}
    for f in (
        facturas.annotate(
            dia=ExtractIsoWeekDay("pedido__fecha_creacion"),
            hora=ExtractHour("pedido__fecha_creacion"),
            fecha=TruncDate("pedido__fecha_creacion"),
        )
        .values("dia", "hora", "fecha")
        .distinct()
        .order_by("fecha")
    ):
        fechas_por_celda.setdefault((f["dia"], f["hora"]), []).append(f["fecha"])

    celdas = []
    for dia in DIAS:
        for hora in HORAS:
            fila = por_celda.get((dia, hora))
            celdas.append({
                "dia": dia,
                "hora": hora,
                "pedidos": fila["pedidos"] if fila else 0,
                "ventas": _dinero(fila["ventas"] if fila else None),
                "fechas": fechas_por_celda.get((dia, hora), []),
            })

    por_dia = [
        {
            "dia": dia,
            "nombre": nombre,
            "pedidos": sum(c["pedidos"] for c in celdas if c["dia"] == dia),
            "ventas": _dinero(sum((c["ventas"] for c in celdas if c["dia"] == dia), CERO)),
        }
        for dia, nombre in DIAS.items()
    ]
    por_hora = [
        {
            "hora": hora,
            "pedidos": sum(c["pedidos"] for c in celdas if c["hora"] == hora),
            "ventas": _dinero(sum((c["ventas"] for c in celdas if c["hora"] == hora), CERO)),
        }
        for hora in HORAS
    ]
    totales = {
        "pedidos": sum(d["pedidos"] for d in por_dia),
        "ventas": _dinero(sum((d["ventas"] for d in por_dia), CERO)),
    }
    return {
        "totales": totales,
        "celdas": celdas,
        "por_dia": por_dia,
        "por_hora": por_hora,
        "dia_pico": _pico(por_dia),
        "hora_pico": _pico(por_hora),
    }


# --- Serializers solo para documentar la respuesta en Swagger ---------------------


def _dinero_campo():
    return serializers.DecimalField(max_digits=14, decimal_places=2)


class CeldaDemandaSerializer(serializers.Serializer):
    dia = serializers.IntegerField(help_text="1 = lunes ... 7 = domingo")
    hora = serializers.IntegerField(help_text="0 a 23, hora local")
    pedidos = serializers.IntegerField()
    ventas = _dinero_campo()
    fechas = serializers.ListField(child=serializers.DateField(), help_text="Días que aportaron pedidos")


class DiaDemandaSerializer(serializers.Serializer):
    dia = serializers.IntegerField()
    nombre = serializers.CharField()
    pedidos = serializers.IntegerField()
    ventas = _dinero_campo()


class HoraDemandaSerializer(serializers.Serializer):
    hora = serializers.IntegerField()
    pedidos = serializers.IntegerField()
    ventas = _dinero_campo()


class TotalesDemandaSerializer(serializers.Serializer):
    pedidos = serializers.IntegerField()
    ventas = _dinero_campo()


class SedeDemandaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class ReporteDemandaSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()
    sede = SedeDemandaSerializer(allow_null=True)
    totales = TotalesDemandaSerializer()
    celdas = CeldaDemandaSerializer(many=True)
    por_dia = DiaDemandaSerializer(many=True)
    por_hora = HoraDemandaSerializer(many=True)
    dia_pico = DiaDemandaSerializer(allow_null=True)
    hora_pico = HoraDemandaSerializer(allow_null=True)
    sin_datos = serializers.BooleanField()
    mensaje = serializers.CharField(allow_null=True)


class ReporteDemandaView(APIView):
    permission_classes = [rol_requerido(ADMINISTRADOR)]

    @extend_schema(
        tags=["Reportes"],
        summary="Patrones de demanda (HU-74)",
        description=(
            "Pedidos y ventas por día de la semana y hora (hora local) en un rango de fechas, para el "
            "mapa de calor y las horas pico. Mismos pedidos válidos que el reporte de ventas. Solo administrador."
        ),
        parameters=[
            OpenApiParameter("desde", str, description="AAAA-MM-DD"),
            OpenApiParameter("hasta", str, description="AAAA-MM-DD"),
            OpenApiParameter("sede", int, description="Solo una sede."),
        ],
        responses={
            200: ReporteDemandaSerializer,
            400: OpenApiResponse(description="Fechas mal escritas, inicio posterior al fin o sede inválida."),
            403: OpenApiResponse(description="No es administrador."),
            404: OpenApiResponse(description="La sede no existe."),
        },
    )
    def get(self, request):
        try:
            desde, hasta, inicio, fin = leer_rango_fechas(request.query_params)
        except RangoFechasInvalido as error:
            return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)

        sede = None
        texto_sede = request.query_params.get("sede")
        if texto_sede:
            if not texto_sede.isdigit():
                return Response({"sede": "Debe ser el id numérico de una sede."}, status=status.HTTP_400_BAD_REQUEST)
            sede = Sede.objects.filter(pk=int(texto_sede)).first()
            if sede is None:
                return Response({"detail": "La sede no existe."}, status=status.HTTP_404_NOT_FOUND)

        datos = patrones_demanda(inicio, fin, sede)
        sin_datos = datos["totales"]["pedidos"] == 0
        datos.update(
            desde=desde,
            hasta=hasta,
            sede={"id": sede.pk, "nombre": sede.nombre} if sede else None,
            sin_datos=sin_datos,
            mensaje="No hay pedidos en el rango seleccionado." if sin_datos else None,
        )
        return Response(ReporteDemandaSerializer(datos).data)
