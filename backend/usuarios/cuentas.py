"""
HU-09 · Desactivar cuentas (también reactivarlas, adelantando HU-80).

Vive en un módulo aparte de views.py para no chocar con login, registro y
direcciones.

Desactivar es poner `Usuario.is_active = False`:
- El login ya rechaza cuentas inactivas (criterio 1).
- SimpleJWT revisa `is_active` en cada petición, así que el token que tenga
  abierto deja de servir en su siguiente acción, y tampoco puede renovarlo
  (criterio 2).
- No se borra nada: datos y pedidos se conservan (criterio 3).
"""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers

from .models import Repartidor, Usuario
from .permissions import rol_requerido
from .roles import ADMINISTRADOR, ROLES_PERSONAL, obtener_rol

CLIENTE = "cliente"
PERSONAL = "personal"


def rol_de_cuenta(usuario):
    """Rol de personal, "cliente" o None. Tolera grupos guardados en mayúsculas."""
    rol = obtener_rol(usuario)
    if rol:
        return rol
    grupos = {nombre.lower() for nombre in usuario.groups.values_list("name", flat=True)}
    for posible in ROLES_PERSONAL:
        if posible in grupos:
            return posible
    if hasattr(usuario, "cliente"):
        return CLIENTE
    return None


class CuentaSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()
    tipo = serializers.SerializerMethodField()
    rol = serializers.SerializerMethodField()
    sede = serializers.SerializerMethodField()
    activa = serializers.BooleanField(source="is_active")
    es_usted = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "tipo", "rol", "sede", "activa", "es_usted"]
        read_only_fields = ["id", "email"]

    def get_nombre(self, usuario) -> str:
        perfil = getattr(usuario, "empleado", None) or getattr(usuario, "cliente", None)
        if perfil is not None:
            return f"{perfil.nombres} {perfil.apellidos}"
        return usuario.get_full_name() or usuario.email

    def get_rol(self, usuario) -> str | None:
        return rol_de_cuenta(usuario)

    def get_tipo(self, usuario) -> str | None:
        rol = rol_de_cuenta(usuario)
        if rol is None:
            return None
        return CLIENTE if rol == CLIENTE else PERSONAL

    def get_sede(self, usuario) -> str | None:
        empleado = getattr(usuario, "empleado", None)
        return empleado.sede.nombre if empleado and empleado.sede_id else None

    def get_es_usted(self, usuario) -> bool:
        request = self.context.get("request")
        return bool(request) and request.user.pk == usuario.pk

    def validate_activa(self, activa):
        request = self.context["request"]
        if not activa and self.instance is not None and self.instance.pk == request.user.pk:
            raise serializers.ValidationError("No puedes desactivar tu propia cuenta.")
        return activa

    def validate(self, attrs):
        if "is_active" not in attrs:
            raise serializers.ValidationError({"activa": "Indica si la cuenta queda activa."})
        return attrs

    def update(self, usuario, validated_data):
        usuario.is_active = validated_data["is_active"]
        usuario.save(update_fields=["is_active"])
        if not usuario.is_active:
            # Un repartidor desactivado no puede seguir recibiendo pedidos.
            Repartidor.objects.filter(empleado__usuario=usuario).update(disponible=False)
        return usuario


def cuentas():
    return Usuario.objects.select_related("empleado__sede", "cliente").prefetch_related("groups")


@extend_schema(
    parameters=[
        OpenApiParameter("tipo", str, enum=[CLIENTE, PERSONAL], description="Clientes o personal."),
        OpenApiParameter("activa", bool, description="true: activas · false: desactivadas."),
        OpenApiParameter("buscar", str, description="Busca por correo, nombres o apellidos."),
    ]
)
class CuentasView(generics.ListAPIView):
    """GET /api/usuarios/cuentas/ · Clientes y personal con el estado de su cuenta."""

    serializer_class = CuentaSerializer
    permission_classes = [rol_requerido(ADMINISTRADOR)]
    pagination_class = None

    def get_queryset(self):
        consulta = cuentas().order_by("-is_active", "email")
        parametros = self.request.query_params

        tipo = parametros.get("tipo")
        if tipo == CLIENTE:
            consulta = consulta.filter(cliente__isnull=False)
        elif tipo == PERSONAL:
            consulta = consulta.filter(Q(empleado__isnull=False) | Q(groups__isnull=False)).filter(
                cliente__isnull=True
            )

        activa = parametros.get("activa")
        if activa is not None:
            consulta = consulta.filter(is_active=activa.lower() in ("true", "1"))

        buscar = parametros.get("buscar", "").strip()
        if buscar:
            consulta = consulta.filter(
                Q(email__icontains=buscar)
                | Q(empleado__nombres__icontains=buscar)
                | Q(empleado__apellidos__icontains=buscar)
                | Q(cliente__nombres__icontains=buscar)
                | Q(cliente__apellidos__icontains=buscar)
            )
        return consulta.distinct()


class CuentaView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/usuarios/cuentas/<id>/
    PATCH /api/usuarios/cuentas/<id>/  {"activa": false}  → desactiva (true reactiva).
    """

    serializer_class = CuentaSerializer
    permission_classes = [rol_requerido(ADMINISTRADOR)]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return cuentas()
