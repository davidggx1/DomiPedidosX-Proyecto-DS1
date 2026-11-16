"""
Alternate sede or next slot (HU-62)

When a customer cannot order from his sede because it is saturated (100% of its
slot) or has no slot for the current day and hour (HU-61), the checkout asks here
for a way out:

- alternativas: the other active sedes that cover his address and have free
  capacity right now, the nearest first. Each one says which products of his cart
  it does not have available
- siguiente_franja: the exact moment the sede starts its next capacity slot

They are the same rules the order confirmation uses (coverage of the zone and
capacity), so what is suggested here is what the order will accept. Opening hours
and holidays are not used because the confirmation does not check them either
"""
from datetime import datetime, timedelta

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from menu.disponibilidad import productos_no_disponibles
from sedes.esquemas import ErrorDetalleSerializer
from sedes.models import CapacidadSede, Sede
from sedes.views import calcular_distancia_haversine
from usuarios.models import DireccionEntrega
from usuarios.roles import obtener_rol

from . import capacidad
from .servicios import _zona_de_cobertura

DIAS_DE_BUSQUEDA = 7

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _dias_de(franja):
    return [d.strip().lower() for d in franja.dias_semana.split(",") if d.strip()]


def proximo_inicio_de_franja(sede, ahora=None):
    """
    Next moment a capacity slot of the sede starts (a datetime), looking at the
    rest of today and the next 7 days. None if the sede has no slot in that time.
    A slot is free by then: the orders that fill it now will be finished
    """
    ahora = ahora or timezone.localtime()
    franjas = list(CapacidadSede.objects.filter(sede=sede))

    for desplazamiento in range(DIAS_DE_BUSQUEDA + 1):
        fecha = ahora.date() + timedelta(days=desplazamiento)
        dia = capacidad.DIAS[fecha.weekday()]
        inicios = sorted(
            franja.hora_inicio
            for franja in franjas
            if dia in _dias_de(franja)
            and (desplazamiento > 0 or franja.hora_inicio > ahora.time())
        )
        if inicios:
            return datetime.combine(fecha, inicios[0], tzinfo=ahora.tzinfo)
    return None


def texto_de_inicio(inicio, ahora=None):
    """'hoy a las 3:00 p. m.', 'mañana a las 11:00 a. m.' or 'el lunes 16 de noviembre a las 11:00 a. m.'"""
    ahora = ahora or timezone.localtime()
    hora = inicio.hour % 12 or 12
    sufijo = "a. m." if inicio.hour < 12 else "p. m."
    reloj = f"{hora}:{inicio.minute:02d} {sufijo}"
    articulo = "a la" if hora == 1 else "a las"

    dias = (inicio.date() - ahora.date()).days
    if dias == 0:
        return f"hoy {articulo} {reloj}"
    if dias == 1:
        return f"mañana {articulo} {reloj}"
    fecha = f"{DIAS_ES[inicio.weekday()]} {inicio.day} de {MESES_ES[inicio.month - 1]}"
    return f"el {fecha} {articulo} {reloj}"


def sedes_alternativas(sede, direccion, productos=()):
    """
    Other active sedes that cover the address and have free capacity now, the
    nearest first. The data of the zone (fee, minimum, time) is the one the order
    will be charged with
    """
    alternativas = []
    for otra in Sede.objects.filter(activa=True).exclude(pk=sede.pk).order_by("nombre"):
        zona = _zona_de_cobertura(otra, direccion)
        if zona is None:
            continue
        estado = capacidad.estado_capacidad(otra)
        if estado["estado"] != capacidad.DISPONIBLE:
            continue
        distancia = calcular_distancia_haversine(
            direccion.latitud, direccion.longitud, zona.centro_latitud, zona.centro_longitud
        )
        alternativas.append(
            {
                "sede": {"id": otra.pk, "nombre": otra.nombre, "direccion": otra.direccion},
                "distancia_km": round(distancia, 2),
                "tarifa_domicilio": float(zona.tarifa_domicilio),
                "pedido_minimo": float(zona.pedido_minimo),
                "tiempo_estimado": zona.tiempo_estimado,
                "cupos_libres": estado["maximo"] - estado["activos"],
                "no_disponibles": productos_no_disponibles(otra, productos) if productos else [],
            }
        )
    return sorted(alternativas, key=lambda alternativa: alternativa["distancia_km"])


class AlternativasSolicitudSerializer(serializers.Serializer):
    sede_id = serializers.IntegerField(help_text="Sede a la que el cliente no puede pedir.")
    direccion_id = serializers.IntegerField(help_text="Dirección de entrega del cliente.")
    productos = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        max_length=100,
        help_text="Ids de los productos del carrito, para avisar cuáles no tendría la otra sede.",
    )


class AlternativasCapacidadView(APIView):
    """POST /api/pedidos/alternativas-capacidad/ (HU-62)"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Capacidad"],
        summary="Sede alterna o siguiente franja cuando la sede está bloqueada (HU-62)",
        description=(
            "El checkout la consulta cuando la sede del cliente está `saturada` o `sin_franja` "
            "(HU-61). Solo clientes, con su propia dirección.\n\n"
            "- `alternativas`: otras sedes activas que cubren la dirección y tienen cupo libre "
            "ahora, la más cercana primero, con la tarifa, el mínimo y el tiempo de su zona y los "
            "productos del carrito que no tendrían.\n"
            "- `siguiente_franja`: cuándo empieza la próxima franja de capacidad de la sede "
            "(hora exacta y texto), o `null` si no tiene ninguna en los próximos 7 días.\n\n"
            "Si la sede no está bloqueada, `bloqueada` es `false` y no devuelve sugerencias."
        ),
        request=AlternativasSolicitudSerializer,
        responses={
            200: OpenApiResponse(description="Estado de la sede y sugerencias."),
            400: OpenApiResponse(ErrorDetalleSerializer, description="Datos inválidos o dirección ajena."),
            403: OpenApiResponse(ErrorDetalleSerializer, description="Solo los clientes pueden consultarlo."),
            404: OpenApiResponse(ErrorDetalleSerializer, description="La sede no existe o no está activa."),
        },
    )
    def post(self, request):
        es_cliente = obtener_rol(request.user) is None and hasattr(request.user, "cliente")
        if not es_cliente:
            return Response(
                {"detail": "Solo los clientes consultan alternativas de sede."}, status=403
            )

        entrada = AlternativasSolicitudSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        sede = Sede.objects.filter(pk=datos["sede_id"], activa=True).first()
        if sede is None:
            return Response({"detail": "La sede no existe o no está activa."}, status=404)

        direccion = DireccionEntrega.objects.filter(
            pk=datos["direccion_id"], cliente=request.user.cliente, activa=True
        ).first()
        if direccion is None:
            raise ValidationError({"direccion_id": ["La dirección no existe o no es tuya."]})

        ahora = timezone.localtime()
        estado = capacidad.estado_capacidad(sede)
        bloqueada = estado["bloqueado"]

        siguiente = proximo_inicio_de_franja(sede, ahora) if bloqueada else None
        return Response(
            {
                "sede": {"id": sede.pk, "nombre": sede.nombre},
                "capacidad": estado,
                "bloqueada": bloqueada,
                "alternativas": (
                    sedes_alternativas(sede, direccion, datos["productos"]) if bloqueada else []
                ),
                "siguiente_franja": (
                    {"inicio": siguiente.isoformat(), "texto": texto_de_inicio(siguiente, ahora)}
                    if siguiente
                    else None
                ),
            }
        )
