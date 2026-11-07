"""
Pedidos del día por sede (HU-67).

Resumen para supervisar la operación: cuántos pedidos lleva cada sede hoy
y cuántos hay en cada estado del flujo.

- "Hoy" es el día local (TIME_ZONE = America/Bogota), de 00:00 a 23:59.
- El operador ve solo su sede; el administrador ve las sedes activas o una con ?sede=<id>.
"""
from datetime import datetime, time, timedelta

from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from sedes.models import Sede
from usuarios.permissions import rol_requerido
from usuarios.roles import ADMINISTRADOR, OPERADOR, obtener_rol, obtener_sede

from .models import EstadoPedido, Pedido


def rango_del_dia(fecha):
    """Inicio y fin (exclusivo) del día `fecha` en la zona horaria local."""
    inicio = timezone.make_aware(datetime.combine(fecha, time.min))
    return inicio, inicio + timedelta(days=1)


def resumen_del_dia(sedes, fecha):
    """Total y conteo por estado de los pedidos creados en `fecha`, sede por sede."""
    inicio, fin = rango_del_dia(fecha)
    conteos = (
        Pedido.objects.filter(sede__in=sedes, fecha_creacion__gte=inicio, fecha_creacion__lt=fin)
        .values("sede_id", "estado")
        .annotate(cantidad=Count("id"))
    )
    # Todos los estados aparecen, aunque estén en 0, para que el panel no cambie de forma.
    por_sede = {sede.pk: {estado: 0 for estado in EstadoPedido.values} for sede in sedes}
    for fila in conteos:
        por_sede[fila["sede_id"]][fila["estado"]] = fila["cantidad"]

    return [
        {
            "sede_id": sede.pk,
            "nombre": sede.nombre,
            "total": sum(por_sede[sede.pk].values()),
            "por_estado": por_sede[sede.pk],
        }
        for sede in sedes
    ]


class ResumenDiaView(APIView):
    """
    GET /api/pedidos/resumen-dia/

    {"fecha": "2026-11-06", "sedes": [{"sede_id", "nombre", "total", "por_estado": {estado: n}}]}
    """

    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]

    @extend_schema(
        parameters=[OpenApiParameter("sede", int, description="Solo administrador: una sola sede.")],
        responses=inline_serializer(
            "ResumenDia",
            {
                "fecha": serializers.DateField(),
                "sedes": inline_serializer(
                    "ResumenDiaSede",
                    {
                        "sede_id": serializers.IntegerField(),
                        "nombre": serializers.CharField(),
                        "total": serializers.IntegerField(),
                        "por_estado": serializers.DictField(child=serializers.IntegerField()),
                    },
                    many=True,
                ),
            },
        ),
    )
    def get(self, request):
        sedes = Sede.objects.order_by("nombre")
        if obtener_rol(request.user) == ADMINISTRADOR:
            sede = request.query_params.get("sede")
            if sede is None:
                sedes = sedes.filter(activa=True)
            elif not sede.isdigit():
                return Response(
                    {"sede": "Debe ser el id numérico de una sede."}, status=status.HTTP_400_BAD_REQUEST
                )
            else:
                sedes = sedes.filter(pk=int(sede))
        else:
            propia = obtener_sede(request.user)
            sedes = sedes.filter(pk=propia.pk) if propia else sedes.none()

        hoy = timezone.localdate()
        return Response({"fecha": hoy, "sedes": resumen_del_dia(list(sedes), hoy)})
