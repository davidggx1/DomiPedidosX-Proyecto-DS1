"""
HU-13 · Disponibilidad de productos por sede.

Vive en un módulo aparte (igual que catalogo.py) para no chocar con los
cambios de gestión del menú que reciben views.py y serializers.py.

La disponibilidad es el campo InventarioProducto.disponible: una fila por
producto y sede. Cambiarla en una sede nunca toca las filas de las demás.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from inventario.models import InventarioProducto
from sedes.models import Sede

from .catalogo import producto_disponible
from .models import Producto
from .permissions import EsPersonalDeMenu


def sedes_que_gestiona(usuario):
    """
    None = todas las sedes (administrador). Un operador solo gestiona la sede
    a la que está asignado; sin sede asignada no gestiona ninguna.
    """
    if usuario.is_staff or usuario.groups.filter(name="administrador").exists():
        return None
    empleado = getattr(usuario, "empleado", None)
    if empleado is None or empleado.sede_id is None:
        return set()
    return {empleado.sede_id}


def productos_no_disponibles(sede, ids):
    """Productos que ya no se pueden pedir en la sede: [{id, nombre}]. Lo reutiliza HU-23."""
    ids = set(ids)
    productos = {producto.id: producto for producto in Producto.objects.filter(pk__in=ids)}
    inventarios = {
        inventario.producto_id: inventario
        for inventario in InventarioProducto.objects.filter(sede=sede, producto_id__in=ids)
    }
    resultado = []
    for producto_id in sorted(ids):
        producto = productos.get(producto_id)
        if producto is None:
            resultado.append({"id": producto_id, "nombre": None})
        elif not producto.activo or not producto_disponible(producto, inventarios.get(producto_id)):
            resultado.append({"id": producto_id, "nombre": producto.nombre})
    return resultado


class CambioDisponibilidadSerializer(serializers.Serializer):
    sede = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.filter(activa=True),
        error_messages={
            "required": "Indica la sede.",
            "null": "Indica la sede.",
            "does_not_exist": "La sede no existe o está inactiva.",
            "incorrect_type": "La sede debe ser un id numérico.",
        },
    )
    disponible = serializers.BooleanField(
        error_messages={
            "required": "Indica si el producto queda disponible.",
            "invalid": "El valor de disponible debe ser true o false.",
        }
    )


class DisponibilidadSedeSerializer(serializers.Serializer):
    sede = serializers.IntegerField()
    sede_nombre = serializers.CharField()
    disponible = serializers.BooleanField()
    editable = serializers.BooleanField()


class DisponibilidadProductoView(APIView):
    """
    GET   /api/menu/productos/<id>/disponibilidad/
          Estado del producto en cada sede activa y si el usuario puede cambiarlo.
    PATCH /api/menu/productos/<id>/disponibilidad/  {"sede": 1, "disponible": false}
          Activa o desactiva el producto SOLO en esa sede.
    """

    permission_classes = [EsPersonalDeMenu]

    def _estado(self, producto, usuario):
        gestionables = sedes_que_gestiona(usuario)
        disponibles = set(
            InventarioProducto.objects.filter(producto=producto, disponible=True).values_list(
                "sede_id", flat=True
            )
        )
        return [
            {
                "sede": sede.id,
                "sede_nombre": sede.nombre,
                "disponible": sede.id in disponibles,
                "editable": gestionables is None or sede.id in gestionables,
            }
            for sede in Sede.objects.filter(activa=True).order_by("nombre")
        ]

    @extend_schema(responses=DisponibilidadSedeSerializer(many=True))
    def get(self, request, pk):
        producto = get_object_or_404(Producto, pk=pk)
        return Response(self._estado(producto, request.user))

    @extend_schema(
        request=CambioDisponibilidadSerializer,
        responses=DisponibilidadSedeSerializer(many=True),
    )
    def patch(self, request, pk):
        producto = get_object_or_404(Producto, pk=pk)
        serializer = CambioDisponibilidadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sede = serializer.validated_data["sede"]

        gestionables = sedes_que_gestiona(request.user)
        if gestionables is not None and sede.id not in gestionables:
            raise PermissionDenied("Solo puedes cambiar la disponibilidad de tu sede.")

        InventarioProducto.objects.update_or_create(
            sede=sede,
            producto=producto,
            defaults={"disponible": serializer.validated_data["disponible"]},
        )
        return Response(self._estado(producto, request.user))


class ValidarCarritoView(APIView):
    """
    POST /api/menu/sedes/<id>/validar-carrito/  {"productos": [1, 2, 3]}

    Hook del carrito: antes de confirmar se revisa que cada producto siga
    disponible en la sede. El bloqueo al crear el pedido llega con HU-23.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=inline_serializer(
            "ValidarCarritoEntrada",
            {"productos": serializers.ListField(child=serializers.IntegerField())},
        ),
        responses=inline_serializer(
            "ValidarCarritoSalida",
            {
                "valido": serializers.BooleanField(),
                "no_disponibles": serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def post(self, request, sede_pk):
        sede = get_object_or_404(Sede, pk=sede_pk, activa=True)
        ids = request.data.get("productos")
        if not isinstance(ids, list) or not all(
            isinstance(valor, int) and not isinstance(valor, bool) for valor in ids
        ):
            return Response(
                {"productos": "Envía la lista de ids de productos del carrito."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        no_disponibles = productos_no_disponibles(sede, ids)
        return Response({"valido": not no_disponibles, "no_disponibles": no_disponibles})
