"""
HU-17 · Cocina reporta un producto como agotado por falta de insumos.

Vive en un módulo aparte (igual que disponibilidad.py y catalogo.py) para no
chocar con los cambios de gestión del menú en views.py.

- Marcar agotado pone InventarioProducto.disponible = False SOLO en la sede de
  quien reporta (criterio 1). Con eso el menú del cliente lo muestra como no
  disponible y el carrito y la confirmación del pedido lo rechazan (criterio 3),
  porque todos usan catalogo.producto_disponible.
- Se guarda un ReporteAgotado (producto, sede, usuario, hora exacta) y, al
  confirmarse la transacción, se avisa por WebSocket a los operadores de la sede
  por el mismo socket del panel (criterio 2).
- Volver a habilitarlo es tarea del operador con la disponibilidad (HU-13).
  Cuando la fila vuelve a quedar disponible, el reporte se marca resuelto y
  los operadores reciben "agotado_resuelto" para sacarlo de su lista.
- El operador ve los reportes pendientes en su Inventario, aunque no estuviera
  conectado cuando llegó el aviso.

API:
    GET  /api/menu/cocina/productos/?q=<texto>       cocina
    POST /api/menu/cocina/productos/<id>/agotado/    cocina
    GET  /api/inventario/agotados/?sede=<id>         operador (su sede) / administrador
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from inventario.models import InventarioInsumo, InventarioProducto, ReporteAgotado
from usuarios.roles import COCINA, nombre_para_mostrar, obtener_rol, obtener_sede

from .catalogo import producto_disponible
from .disponibilidad import sedes_que_gestiona
from .models import Producto
from .permissions import EsPersonalDeMenu

logger = logging.getLogger(__name__)

TIPO_EVENTO = "producto_agotado"
TIPO_EVENTO_RESUELTO = "agotado_resuelto"


class EsCocinaConSede(permissions.BasePermission):
    """Solo personal de cocina asignado a una sede."""

    message = "Solo el personal de cocina con sede asignada puede reportar agotados."

    def has_permission(self, request, view):
        usuario = request.user
        if not usuario or not usuario.is_authenticated:
            return False
        return obtener_rol(usuario) == COCINA and obtener_sede(usuario) is not None


def datos_reporte(reporte):
    """Reporte como dict para la API y el evento del WebSocket."""
    return {
        "id": reporte.pk,
        "sede": reporte.sede_id,
        "producto": reporte.producto_id,
        "producto_nombre": reporte.producto.nombre,
        "usuario": reporte.usuario_id,
        "usuario_nombre": nombre_para_mostrar(reporte.usuario),
        "fecha_hora": timezone.localtime(reporte.fecha_hora).isoformat(),
        "resuelto_en": timezone.localtime(reporte.resuelto_en).isoformat() if reporte.resuelto_en else None,
    }


def enviar_a_operadores(sede_id, datos):
    """Envía `datos` a los operadores de la sede al confirmarse la transacción. Nunca rompe la acción."""
    evento = {"type": "pedido.evento", "data": datos}

    def enviar():
        try:
            # Importado aquí: pedidos depende de menu, no al revés.
            from pedidos.consumers import grupo_sede

            async_to_sync(get_channel_layer().group_send)(grupo_sede(sede_id), evento)
        except Exception:
            logger.exception("No se pudo enviar el aviso %s a la sede %s", datos.get("tipo"), sede_id)

    transaction.on_commit(enviar)


def avisar_operadores(reporte):
    """Envía el reporte nuevo a los operadores de la sede (criterio 2)."""
    enviar_a_operadores(reporte.sede_id, {"tipo": TIPO_EVENTO, "reporte": datos_reporte(reporte)})


@receiver(post_save, sender=InventarioProducto)
def resolver_agotados(sender, instance, **kwargs):
    """Si el producto vuelve a estar disponible en la sede, sus reportes pendientes se resuelven."""
    campos = kwargs.get("update_fields")
    if not instance.disponible or (campos is not None and "disponible" not in campos):
        return
    pendientes = ReporteAgotado.objects.filter(
        sede_id=instance.sede_id, producto_id=instance.producto_id, resuelto_en__isnull=True
    )
    ids = list(pendientes.values_list("pk", flat=True))
    if not ids:
        return
    ReporteAgotado.objects.filter(pk__in=ids).update(resuelto_en=timezone.now())
    enviar_a_operadores(
        instance.sede_id,
        {"tipo": TIPO_EVENTO_RESUELTO, "reportes": ids, "producto": instance.producto_id, "sede": instance.sede_id},
    )


def disponibilidad_en_sede(sede, productos):
    """{producto_id: bool} con la misma regla del menú del cliente."""
    ids = [producto.pk for producto in productos]
    inventarios = {
        inv.producto_id: inv for inv in InventarioProducto.objects.filter(sede=sede, producto_id__in=ids)
    }
    insumos = {inv.insumo_id: inv for inv in InventarioInsumo.objects.filter(sede=sede)}
    return {
        producto.pk: producto_disponible(producto, inventarios.get(producto.pk), insumos)
        for producto in productos
    }


class ProductoCocinaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    categoria = serializers.CharField()
    disponible = serializers.BooleanField()


class ProductosCocinaView(APIView):
    """GET /api/menu/cocina/productos/ · Productos activos y si están disponibles en la sede de cocina."""

    permission_classes = [EsCocinaConSede]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Filtra por nombre (contiene).")],
        responses=ProductoCocinaSerializer(many=True),
    )
    def get(self, request):
        sede = obtener_sede(request.user)
        productos = (
            Producto.objects.filter(activo=True)
            .select_related("categoria")
            .prefetch_related("insumos_requeridos")
            .order_by("categoria__nombre", "nombre")
        )
        busqueda = request.query_params.get("q", "").strip()
        if busqueda:
            productos = productos.filter(nombre__icontains=busqueda)
        productos = list(productos)
        disponibles = disponibilidad_en_sede(sede, productos)
        return Response(
            [
                {
                    "id": producto.pk,
                    "nombre": producto.nombre,
                    "categoria": producto.categoria.nombre,
                    "disponible": disponibles[producto.pk],
                }
                for producto in productos
            ]
        )


class MarcarAgotadoView(APIView):
    """POST /api/menu/cocina/productos/<id>/agotado/ · Saca el producto del menú de la sede (HU-17)."""

    permission_classes = [EsCocinaConSede]

    @extend_schema(
        request=None,
        responses=inline_serializer(
            "ReporteAgotado",
            {
                "id": serializers.IntegerField(),
                "sede": serializers.IntegerField(),
                "producto": serializers.IntegerField(),
                "producto_nombre": serializers.CharField(),
                "usuario": serializers.IntegerField(),
                "usuario_nombre": serializers.CharField(),
                "fecha_hora": serializers.DateTimeField(),
            },
        ),
    )
    def post(self, request, pk):
        sede = obtener_sede(request.user)
        producto = get_object_or_404(
            Producto.objects.prefetch_related("insumos_requeridos"), pk=pk, activo=True
        )

        with transaction.atomic():
            inventario = (
                InventarioProducto.objects.select_for_update().filter(sede=sede, producto=producto).first()
            )
            if not disponibilidad_en_sede(sede, [producto])[producto.pk]:
                return Response(
                    {"detail": f"{producto.nombre} ya no está disponible en esta sede.", "codigo": "ya_agotado"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Disponible implica que la fila existe (sin fila no se vende en la sede).
            inventario.disponible = False
            inventario.save(update_fields=["disponible", "fecha_actualizacion"])

            reporte = ReporteAgotado.objects.create(sede=sede, producto=producto, usuario=request.user)
            avisar_operadores(reporte)

        return Response(datos_reporte(reporte), status=status.HTTP_201_CREATED)


class AgotadosPendientesView(APIView):
    """
    GET /api/inventario/agotados/

    Productos que cocina reportó agotados y siguen sin habilitarse, del más
    reciente al más antiguo, una vez por producto y sede. El operador ve su sede; el administrador todas,
    o una con ?sede=<id>.
    """

    permission_classes = [EsPersonalDeMenu]

    @extend_schema(
        parameters=[OpenApiParameter("sede", int, description="Filtra por id de sede.")],
        responses=inline_serializer(
            "ReporteAgotadoPendiente",
            {
                "id": serializers.IntegerField(),
                "sede": serializers.IntegerField(),
                "producto": serializers.IntegerField(),
                "producto_nombre": serializers.CharField(),
                "usuario": serializers.IntegerField(),
                "usuario_nombre": serializers.CharField(),
                "fecha_hora": serializers.DateTimeField(),
                "resuelto_en": serializers.DateTimeField(allow_null=True),
            },
            many=True,
        ),
    )
    def get(self, request):
        reportes = ReporteAgotado.objects.filter(
            resuelto_en__isnull=True, producto__activo=True
        ).select_related("producto", "usuario__empleado")
        gestionables = sedes_que_gestiona(request.user)
        if gestionables is not None:
            reportes = reportes.filter(sede_id__in=gestionables)

        sede = request.query_params.get("sede")
        if sede not in (None, ""):
            if not sede.isdigit():
                return Response({"sede": "La sede debe ser un id numérico."}, status=status.HTTP_400_BAD_REQUEST)
            reportes = reportes.filter(sede_id=int(sede))

        # Un producto aparece una sola vez por sede: con su reporte más reciente.
        vistos, resultado = set(), []
        for reporte in reportes.order_by("-fecha_hora", "-id"):
            clave = (reporte.sede_id, reporte.producto_id)
            if clave not in vistos:
                vistos.add(clave)
                resultado.append(datos_reporte(reporte))
        return Response(resultado)
