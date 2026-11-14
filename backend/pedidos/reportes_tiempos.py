"""
HU-72 · Reportes de tiempos y desempeño (administrador).

GET /api/pedidos/reportes/tiempos/?desde=AAAA-MM-DD&hasta=AAAA-MM-DD&sede=<id>

Solo cuenta pedidos con estado final "Entregado" (criterio 3), creados en el rango
(días locales, los dos incluidos; sin fechas, los últimos 7 días). Sin `sede`: todas.

Tiempos, sacados de las marcas de tiempo del historial de estados (HistorialEstadoPedido):
- Fases (criterio 1), promedio en minutos:
    aprobación   pendiente de aprobación -> recibido    (solo pedidos web: los del
                                                         operador nacen ya recibidos)
    preparación  recibido -> listo para despacho        (espera + cocina)
    despacho     listo para despacho -> en camino       (el repartidor lo recoge y sale)
    entrega      en camino -> entregado
- Repartidores (criterio 2): pedidos entregados, ciclo promedio (creación -> entrega,
  igual que el "tiempo promedio de entrega" de la HU-70) y tiempo de reparto promedio
  (listo para despacho -> entregado: lo que depende del repartidor).

Si no hay pedidos entregados en el rango, `sin_datos` es true y `mensaje` lo explica
(criterio 4). Inicio posterior al fin -> 400.
"""
from collections import defaultdict

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from sedes.models import Sede
from usuarios.permissions import rol_requerido
from usuarios.roles import ADMINISTRADOR

from .models import EstadoPedido as E, Pedido
from .rango_fechas import RangoFechasInvalido, leer_rango_fechas

FASES = [
    ("aprobacion", "Aprobación", E.PENDIENTE_APROBACION, E.RECIBIDO),
    ("preparacion", "Preparación en cocina", E.RECIBIDO, E.LISTO_DESPACHO),
    ("despacho", "Despacho", E.LISTO_DESPACHO, E.EN_CAMINO),
    ("entrega", "Entrega", E.EN_CAMINO, E.ENTREGADO),
]


def _minutos(desde, hasta):
    return (hasta - desde).total_seconds() / 60


def _promedio(valores):
    return round(sum(valores) / len(valores), 1) if valores else None


def _nombre_repartidor(repartidor):
    empleado = repartidor.empleado
    return f"{empleado.nombres} {empleado.apellidos}".strip()


def _primeras_marcas(pedido):
    """Primera vez que el pedido pasó por cada estado."""
    marcas = {}
    for paso in pedido.historial_estados.all():
        if paso.estado not in marcas or paso.fecha_hora < marcas[paso.estado]:
            marcas[paso.estado] = paso.fecha_hora
    return marcas


def reporte_tiempos(inicio, fin, sede=None):
    pedidos = Pedido.objects.filter(
        estado=E.ENTREGADO, fecha_creacion__gte=inicio, fecha_creacion__lt=fin
    ).select_related("repartidor__empleado").prefetch_related("historial_estados")
    if sede is not None:
        pedidos = pedidos.filter(sede=sede)

    por_fase = defaultdict(list)
    ciclos = []
    repartidores = {}

    for pedido in pedidos:
        marcas = _primeras_marcas(pedido)
        entregado = marcas.get(E.ENTREGADO)
        if entregado is None:  # entregado sin marca en el historial: no hay cómo medirlo
            continue

        for clave, _, estado_inicio, estado_fin in FASES:
            if estado_inicio in marcas and estado_fin in marcas:
                por_fase[clave].append(_minutos(marcas[estado_inicio], marcas[estado_fin]))

        ciclo = _minutos(pedido.fecha_creacion, entregado)
        ciclos.append(ciclo)

        if pedido.repartidor_id:
            fila = repartidores.setdefault(pedido.repartidor_id, {
                "id": pedido.repartidor_id,
                "nombre": _nombre_repartidor(pedido.repartidor),
                "ciclos": [],
                "repartos": [],
            })
            fila["ciclos"].append(ciclo)
            if E.LISTO_DESPACHO in marcas:
                fila["repartos"].append(_minutos(marcas[E.LISTO_DESPACHO], entregado))

    filas_repartidores = sorted(
        (
            {
                "id": fila["id"],
                "nombre": fila["nombre"],
                "pedidos_entregados": len(fila["ciclos"]),
                "ciclo_promedio_minutos": _promedio(fila["ciclos"]),
                "reparto_promedio_minutos": _promedio(fila["repartos"]),
            }
            for fila in repartidores.values()
        ),
        key=lambda fila: (-fila["pedidos_entregados"], fila["ciclo_promedio_minutos"], fila["nombre"]),
    )

    return {
        "pedidos_entregados": len(ciclos),
        "ciclo_promedio_minutos": _promedio(ciclos),
        "fases": [
            {
                "fase": clave,
                "nombre": nombre,
                "desde_estado": estado_inicio,
                "hasta_estado": estado_fin,
                "promedio_minutos": _promedio(por_fase[clave]),
                "pedidos": len(por_fase[clave]),
            }
            for clave, nombre, estado_inicio, estado_fin in FASES
        ],
        "repartidores": filas_repartidores,
    }


# --- Respuesta documentada (Swagger) ------------------------------------------------


class FaseSerializer(serializers.Serializer):
    fase = serializers.ChoiceField(choices=[clave for clave, *_ in FASES])
    nombre = serializers.CharField()
    desde_estado = serializers.CharField()
    hasta_estado = serializers.CharField()
    promedio_minutos = serializers.FloatField(allow_null=True, help_text="null si ningún pedido pasó por la fase.")
    pedidos = serializers.IntegerField(help_text="Pedidos con las dos marcas de la fase.")


class DesempenoRepartidorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    pedidos_entregados = serializers.IntegerField()
    ciclo_promedio_minutos = serializers.FloatField(help_text="Creación -> entrega.")
    reparto_promedio_minutos = serializers.FloatField(allow_null=True, help_text="Listo para despacho -> entrega.")


class SedeReporteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class ReporteTiemposSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()
    sede = SedeReporteSerializer(allow_null=True)
    sin_datos = serializers.BooleanField()
    mensaje = serializers.CharField(allow_null=True)
    pedidos_entregados = serializers.IntegerField()
    ciclo_promedio_minutos = serializers.FloatField(allow_null=True)
    fases = FaseSerializer(many=True)
    repartidores = DesempenoRepartidorSerializer(many=True)


class ReporteTiemposView(APIView):
    permission_classes = [rol_requerido(ADMINISTRADOR)]

    @extend_schema(
        tags=["Reportes"],
        summary="Reporte de tiempos y desempeño (HU-72)",
        description=(
            "Promedio en minutos de cada fase (aprobación, preparación, despacho, entrega) y desempeño "
            "de cada repartidor. Solo pedidos entregados, creados entre `desde` y `hasta` (incluidos; "
            "por defecto los últimos 7 días). Solo administrador."
        ),
        parameters=[
            OpenApiParameter("desde", str, description="AAAA-MM-DD"),
            OpenApiParameter("hasta", str, description="AAAA-MM-DD"),
            OpenApiParameter("sede", int, description="Solo una sede."),
        ],
        responses={
            200: ReporteTiemposSerializer,
            400: OpenApiResponse(description="Fechas mal escritas, inicio posterior al fin o sede no numérica."),
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

        datos = reporte_tiempos(inicio, fin, sede)
        sin_datos = datos["pedidos_entregados"] == 0
        datos.update(
            desde=desde,
            hasta=hasta,
            sede={"id": sede.pk, "nombre": sede.nombre} if sede else None,
            sin_datos=sin_datos,
            mensaje="No hay pedidos entregados en el rango seleccionado." if sin_datos else None,
        )
        return Response(ReporteTiemposSerializer(datos).data)
