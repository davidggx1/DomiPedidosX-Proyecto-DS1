"""
HU-71 · Reportes de ventas (administrador).

GET /api/pedidos/reportes/ventas/?agrupar=producto|categoria|sede|zona&desde=AAAA-MM-DD&hasta=AAAA-MM-DD&sede=<id>

Pedidos válidos: los no cancelados que tienen factura, creados en el rango (días
locales, los dos incluidos; sin fechas, los últimos 7 días). Es la misma regla de
"ventas" del panel del día (HU-70), así las cifras coinciden.

- `totales` siempre sale de las facturas: lo facturado (criterio 2).
- Por sede y por zona, cada grupo suma el total facturado de sus pedidos, así la
  suma de los grupos es igual al total. Los pedidos del operador no tienen zona y
  van al grupo "Sin zona".
- Por producto y por categoría, cada grupo suma el subtotal de sus líneas (precio
  con tamaño y adiciones). El descuento y el domicilio son de la factura, no de
  una línea, por eso van en `conciliacion`: líneas − descuentos + domicilio
  (+ ajustes) = total facturado. Los combos son un grupo propio ("Combos" por
  categoría).

Inicio posterior al fin -> 400 (criterio 3). Sin ventas en el rango, `sin_datos`
es true y `mensaje` lo explica, para avisar antes de pintar la tabla (criterio 4).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Q, Sum
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from sedes.models import Sede
from usuarios.permissions import rol_requerido
from usuarios.roles import ADMINISTRADOR

from .models import DetallePedido, EstadoPedido, Factura
from .rango_fechas import RangoFechasInvalido, leer_rango_fechas

CERO = Decimal("0")
AGRUPACIONES = ("producto", "categoria", "sede", "zona")
SIN_ZONA = "Sin zona (mostrador o teléfono)"
COMBOS = "Combos"


def _dinero(valor):
    return (valor or CERO).quantize(Decimal("0.01"))


def _porcentaje(parte, total):
    if not total:
        return CERO
    return (Decimal(parte) * 100 / total).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _validos(inicio, fin, sede, prefijo="pedido__"):
    """Pedidos válidos del rango, vistos desde Factura o DetallePedido (`pedido__...`)."""
    filtro = Q(**{
        f"{prefijo}fecha_creacion__gte": inicio,
        f"{prefijo}fecha_creacion__lt": fin,
        f"{prefijo}factura__isnull": False,
    }) & ~Q(**{f"{prefijo}estado": EstadoPedido.CANCELADO})
    if sede is not None:
        filtro &= Q(**{f"{prefijo}sede": sede})
    return filtro


def _grupos_por_factura(facturas, agrupar):
    campos = ("pedido__sede_id", "pedido__sede__nombre") if agrupar == "sede" else (
        "pedido__zona_cobertura_id", "pedido__zona_cobertura__nombre", "pedido__sede__nombre",
    )
    filas = facturas.values(*campos).annotate(pedidos=Count("pedido_id"), ventas=Sum("total"))
    grupos = []
    for f in filas:
        if agrupar == "sede":
            clave, nombre = f["pedido__sede_id"], f["pedido__sede__nombre"]
        elif f["pedido__zona_cobertura_id"] is None:
            clave, nombre = f"sin-zona-{f['pedido__sede__nombre']}", f"{SIN_ZONA} · {f['pedido__sede__nombre']}"
        else:
            clave = f["pedido__zona_cobertura_id"]
            nombre = f"{f['pedido__zona_cobertura__nombre']} · {f['pedido__sede__nombre']}"
        grupos.append({"clave": str(clave), "nombre": nombre, "pedidos": f["pedidos"],
                       "unidades": None, "ventas": f["ventas"]})
    return grupos


def _grupos_por_linea(lineas, agrupar):
    if agrupar == "producto":
        campos = ("producto_id", "producto__nombre", "combo_id", "combo__nombre")
    else:
        campos = ("producto__categoria_id", "producto__categoria__nombre")
    filas = lineas.values(*campos).annotate(
        pedidos=Count("pedido_id", distinct=True), unidades=Sum("cantidad"), ventas=Sum("subtotal"),
    )
    grupos = []
    for f in filas:
        if agrupar == "producto":
            if f["producto_id"] is not None:
                clave, nombre = f"p-{f['producto_id']}", f["producto__nombre"]
            else:
                clave, nombre = f"c-{f['combo_id']}", f"Combo: {f['combo__nombre']}"
        elif f["producto__categoria_id"] is None:
            clave, nombre = "combos", COMBOS
        else:
            clave, nombre = str(f["producto__categoria_id"]), f["producto__categoria__nombre"]
        grupos.append({"clave": clave, "nombre": nombre, "pedidos": f["pedidos"],
                       "unidades": f["unidades"], "ventas": f["ventas"]})
    return grupos


def reporte_ventas(inicio, fin, agrupar, sede=None):
    validos = _validos(inicio, fin, sede)
    facturas = Factura.objects.filter(validos)

    suma = facturas.aggregate(
        pedidos=Count("pk"), subtotal=Sum("subtotal"), descuentos=Sum("valor_descuento"),
        domicilio=Sum("costo_domicilio"), total=Sum("total"),
    )
    pedidos = suma["pedidos"]
    totales = {
        "pedidos": pedidos,
        "subtotal": _dinero(suma["subtotal"]),
        "descuentos": _dinero(suma["descuentos"]),
        "domicilio": _dinero(suma["domicilio"]),
        "total": _dinero(suma["total"]),
        "ticket_promedio": _dinero(suma["total"] / pedidos) if pedidos else _dinero(CERO),
    }

    conciliacion = None
    if agrupar in ("sede", "zona"):
        grupos = _grupos_por_factura(facturas, agrupar)
    else:
        grupos = _grupos_por_linea(DetallePedido.objects.filter(validos), agrupar)
        lineas = _dinero(sum((g["ventas"] for g in grupos), CERO))
        conciliacion = {
            "lineas": lineas,
            "descuentos": totales["descuentos"],
            "domicilio": totales["domicilio"],
            # Pedidos viejos del operador guardaban la línea sin adiciones; la diferencia queda a la vista.
            "ajustes": totales["subtotal"] - lineas,
            "total": totales["total"],
        }

    base = sum((g["ventas"] for g in grupos), CERO)
    for g in grupos:
        g["ventas"] = _dinero(g["ventas"])
        g["porcentaje"] = _porcentaje(g["ventas"], base)
    grupos.sort(key=lambda g: (-g["ventas"], g["nombre"]))

    return {"agrupar": agrupar, "totales": totales, "grupos": grupos, "conciliacion": conciliacion}


# --- Serializers solo para documentar la respuesta en Swagger ---------------------


def _dinero_campo():
    return serializers.DecimalField(max_digits=14, decimal_places=2)


class TotalesVentasSerializer(serializers.Serializer):
    pedidos = serializers.IntegerField()
    subtotal = _dinero_campo()
    descuentos = _dinero_campo()
    domicilio = _dinero_campo()
    total = _dinero_campo()
    ticket_promedio = _dinero_campo()


class GrupoVentasSerializer(serializers.Serializer):
    clave = serializers.CharField()
    nombre = serializers.CharField()
    pedidos = serializers.IntegerField()
    unidades = serializers.IntegerField(allow_null=True)
    ventas = _dinero_campo()
    porcentaje = serializers.DecimalField(max_digits=5, decimal_places=1)


class ConciliacionVentasSerializer(serializers.Serializer):
    lineas = _dinero_campo()
    descuentos = _dinero_campo()
    domicilio = _dinero_campo()
    ajustes = _dinero_campo()
    total = _dinero_campo()


class SedeReporteSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class ReporteVentasSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()
    sede = SedeReporteSerializer(allow_null=True)
    agrupar = serializers.ChoiceField(choices=AGRUPACIONES)
    totales = TotalesVentasSerializer()
    grupos = GrupoVentasSerializer(many=True)
    conciliacion = ConciliacionVentasSerializer(allow_null=True)
    sin_datos = serializers.BooleanField()
    mensaje = serializers.CharField(allow_null=True)


class ReporteVentasView(APIView):
    permission_classes = [rol_requerido(ADMINISTRADOR)]

    @extend_schema(
        tags=["Reportes"],
        summary="Reporte de ventas (HU-71)",
        description=(
            "Ventas de pedidos no cancelados agrupadas por producto, categoría, sede o zona, en un rango "
            "de fechas (por defecto los últimos 7 días). Solo administrador."
        ),
        parameters=[
            OpenApiParameter("agrupar", str, enum=list(AGRUPACIONES), description="Por defecto: producto."),
            OpenApiParameter("desde", str, description="AAAA-MM-DD"),
            OpenApiParameter("hasta", str, description="AAAA-MM-DD"),
            OpenApiParameter("sede", int, description="Solo una sede."),
        ],
        responses={
            200: ReporteVentasSerializer,
            400: OpenApiResponse(description="Fechas mal escritas, inicio posterior al fin, agrupación o sede inválida."),
            403: OpenApiResponse(description="No es administrador."),
            404: OpenApiResponse(description="La sede no existe."),
        },
    )
    def get(self, request):
        try:
            desde, hasta, inicio, fin = leer_rango_fechas(request.query_params)
        except RangoFechasInvalido as error:
            return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)

        agrupar = request.query_params.get("agrupar") or "producto"
        if agrupar not in AGRUPACIONES:
            return Response(
                {"agrupar": "Agrupa por producto, categoria, sede o zona."}, status=status.HTTP_400_BAD_REQUEST
            )

        sede = None
        texto_sede = request.query_params.get("sede")
        if texto_sede:
            if not texto_sede.isdigit():
                return Response({"sede": "Debe ser el id numérico de una sede."}, status=status.HTTP_400_BAD_REQUEST)
            sede = Sede.objects.filter(pk=int(texto_sede)).first()
            if sede is None:
                return Response({"detail": "La sede no existe."}, status=status.HTTP_404_NOT_FOUND)

        datos = reporte_ventas(inicio, fin, agrupar, sede)
        sin_datos = datos["totales"]["pedidos"] == 0
        datos.update(
            desde=desde,
            hasta=hasta,
            sede={"id": sede.pk, "nombre": sede.nombre} if sede else None,
            sin_datos=sin_datos,
            mensaje="No hay ventas en el rango seleccionado." if sin_datos else None,
        )
        return Response(ReporteVentasSerializer(datos).data)
