"""
HU-69 · El administrador consulta la información de los clientes.

Vive en un módulo aparte, como cuentas.py.

- GET /api/usuarios/clientes/?buscar=  busca por nombre, correo o teléfono y
  devuelve contacto, estado de la cuenta y fecha de registro (criterio 1).
- GET /api/usuarios/clientes/<id>/  la ficha del cliente con todo su historial
  de pedidos, incluidos los cancelados (criterio 2).

Los serializers listan sus campos uno por uno: nunca salen la contraseña, su
hash, el último inicio de sesión ni permisos (criterio 3).
"""
from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers

from pedidos.models import Pedido
from pedidos.serializers import nombre_linea

from .models import Cliente, DireccionEntrega
from .permissions import rol_requerido
from .roles import ADMINISTRADOR


class ClienteSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    email = serializers.EmailField(source="usuario.email", read_only=True)
    activa = serializers.BooleanField(source="usuario.is_active", read_only=True)
    fecha_registro = serializers.DateTimeField(source="usuario.date_joined", read_only=True)
    total_pedidos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cliente
        fields = [
            "id", "nombre", "email", "celular", "tipo_documento", "num_documento",
            "activa", "fecha_registro", "total_pedidos",
        ]

    def get_nombre(self, cliente) -> str:
        return f"{cliente.nombres} {cliente.apellidos}"


class DireccionClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DireccionEntrega
        fields = ["id", "alias", "direccion", "barrio", "indicaciones", "es_principal"]


class PedidoHistorialSerializer(serializers.ModelSerializer):
    sede = serializers.CharField(source="sede.nombre", read_only=True)
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    origen_nombre = serializers.CharField(source="get_origen_display", read_only=True)
    total = serializers.DecimalField(
        source="factura.total", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    metodo_pago = serializers.CharField(source="factura.get_metodo_pago_display", read_only=True, default=None)
    resumen = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            "id", "numero_pedido", "fecha_creacion", "sede", "origen", "origen_nombre", "estado",
            "estado_nombre", "total", "metodo_pago", "entrega_direccion", "motivo_cancelacion", "resumen",
        ]

    def get_resumen(self, pedido) -> list[str]:
        return [f"{d.cantidad}x {nombre_linea(d)}" for d in pedido.detalles.all()]


class FichaClienteSerializer(ClienteSerializer):
    fecha_nacimiento = serializers.DateField(read_only=True)
    direcciones = DireccionClienteSerializer(source="direcciones_activas", many=True, read_only=True)
    pedidos = PedidoHistorialSerializer(many=True, read_only=True)

    class Meta(ClienteSerializer.Meta):
        fields = ClienteSerializer.Meta.fields + ["fecha_nacimiento", "direcciones", "pedidos"]


def clientes():
    return Cliente.objects.select_related("usuario").annotate(total_pedidos=Count("pedidos"))


@extend_schema(
    parameters=[OpenApiParameter("buscar", str, description="Nombre, apellido, correo o celular.")]
)
class ClientesView(generics.ListAPIView):
    """GET /api/usuarios/clientes/ · Clientes registrados, del más reciente al más antiguo."""

    serializer_class = ClienteSerializer
    permission_classes = [rol_requerido(ADMINISTRADOR)]
    pagination_class = None

    def get_queryset(self):
        consulta = clientes().order_by("-usuario__date_joined", "-id")
        # Cada palabra debe aparecer en algún campo: "ana perez" encuentra a Ana Pérez.
        for palabra in self.request.query_params.get("buscar", "").split():
            consulta = consulta.filter(
                Q(nombres__icontains=palabra)
                | Q(apellidos__icontains=palabra)
                | Q(usuario__email__icontains=palabra)
                | Q(celular__icontains=palabra)
            )
        return consulta


class FichaClienteView(generics.RetrieveAPIView):
    """GET /api/usuarios/clientes/<id>/ · Ficha del cliente con su historial de pedidos."""

    serializer_class = FichaClienteSerializer
    permission_classes = [rol_requerido(ADMINISTRADOR)]

    def get_queryset(self):
        pedidos = (
            Pedido.objects.select_related("sede", "factura")
            .prefetch_related("detalles__producto", "detalles__producto_tamano", "detalles__combo")
            .order_by("-fecha_creacion", "-id")
        )
        direcciones = DireccionEntrega.objects.filter(activa=True).order_by("-es_principal", "alias", "id")
        return clientes().prefetch_related(
            Prefetch("pedidos", queryset=pedidos),
            Prefetch("direcciones_entrega", queryset=direcciones, to_attr="direcciones_activas"),
        )
