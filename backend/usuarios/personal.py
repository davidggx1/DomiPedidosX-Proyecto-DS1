"""HU-80 · Editar y reactivar cuentas del personal (solo el administrador).

GET/PUT/PATCH /api/usuarios/empleados/<id>/   (<id> es el id del Empleado, el mismo del listado)

- Edita nombres, apellidos, documento, celular, dirección, rol y sede, de cuentas activas o inactivas.
- Cambiar el rol o la sede se aplica en la base de datos (grupos y sede del empleado), que el
  backend consulta en cada petición: el permiso nuevo vale de inmediato y el login siguiente
  devuelve el rol y la sede nuevos.
- `activa` reactiva (o desactiva) la cuenta: una cuenta reactivada vuelve a poder iniciar sesión.
"""
from django.contrib.auth.models import Group
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers

from sedes.models import Sede

from .models import Empleado, Repartidor, TipoDocumento, Usuario
from .permissions import rol_requerido
from .roles import ADMINISTRADOR, REPARTIDOR, ROLES_PERSONAL

ROLES_EDITABLES = ["OPERADOR", "COCINA", "REPARTIDOR", "ADMINISTRADOR"]


def rol_de(usuario):
    """Rol del usuario en mayúsculas ('' si no tiene). Acepta grupos en minúsculas o mayúsculas."""
    nombres = {g.name.lower() for g in usuario.groups.all()}
    for rol in ROLES_PERSONAL:
        if rol in nombres:
            return rol.upper()
    return ""


def _entregas_en_curso(empleado):
    from pedidos.models import EstadoPedido

    perfil = getattr(empleado, "perfil_repartidor", None)
    if perfil is None:
        return False
    return perfil.pedidos_asignados.exclude(
        estado__in=[EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO]
    ).exists()


class EmpleadoEdicionSerializer(serializers.ModelSerializer):
    email = serializers.ReadOnlyField(source="usuario.email")
    rol = serializers.ChoiceField(choices=ROLES_EDITABLES, required=False, write_only=True)
    sede_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    activa = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = Empleado
        fields = [
            "id", "email", "nombres", "apellidos", "tipo_documento", "num_documento",
            "celular", "direccion", "rol", "sede_id", "activa",
        ]
        validators = []  # el documento repetido se valida abajo, con mensaje propio

    def to_representation(self, instance):
        datos = super().to_representation(instance)
        datos["rol"] = rol_de(instance.usuario)
        datos["sede_id"] = instance.sede_id
        datos["sede"] = instance.sede.nombre if instance.sede else None
        datos["activa"] = instance.usuario.is_active
        return datos

    def validate_celular(self, value):
        if len(value) != 10 or not value.isdigit():
            raise serializers.ValidationError("El teléfono debe contener exactamente 10 dígitos numéricos.")
        return value

    def validate(self, attrs):
        empleado = self.instance
        usuario = empleado.usuario
        yo = self.context["request"].user
        rol_actual = rol_de(usuario)

        rol = attrs.get("rol", rol_actual)
        if not rol:
            raise serializers.ValidationError({"rol": "Esta cuenta no tiene rol: elige uno."})

        # Sede: obligatoria para roles operativos.
        if "sede_id" in attrs:
            sede_id = attrs["sede_id"]
        elif rol == ADMINISTRADOR.upper() and "rol" in attrs and rol_actual != rol:
            sede_id = None
        else:
            sede_id = empleado.sede_id
        sede = None
        if rol != ADMINISTRADOR.upper() and not sede_id:
            raise serializers.ValidationError({"sede_id": f"La sede es obligatoria para el rol {rol}."})
        if sede_id:
            sede = Sede.objects.filter(pk=sede_id, activa=True).first()
            if sede is None and sede_id != empleado.sede_id:
                raise serializers.ValidationError(
                    {"sede_id": "La sede seleccionada no existe o se encuentra inactiva."}
                )
            if sede is None:  # conserva la sede actual aunque esté inactiva
                sede = empleado.sede

        # Documento único entre empleados.
        tipo = attrs.get("tipo_documento", empleado.tipo_documento)
        numero = attrs.get("num_documento", empleado.num_documento)
        if Empleado.objects.filter(tipo_documento=tipo, num_documento=numero).exclude(pk=empleado.pk).exists():
            raise serializers.ValidationError(
                {"num_documento": "Ya existe un empleado con este número de documento."}
            )

        cambia_rol = rol != rol_actual
        cambia_sede = sede_id != empleado.sede_id
        desactiva = attrs.get("activa") is False

        # Protecciones sobre la propia cuenta (así nunca se queda el sistema sin administrador).
        if usuario.pk == yo.pk:
            if cambia_rol:
                raise serializers.ValidationError({"rol": "No puedes cambiar tu propio rol."})
            if desactiva:
                raise serializers.ValidationError({"activa": "No puedes desactivar tu propia cuenta."})
        # Un repartidor con entregas en curso no puede cambiar de rol ni de sede.
        es_repartidor = rol_actual == REPARTIDOR.upper()
        if es_repartidor and (cambia_rol or cambia_sede) and _entregas_en_curso(empleado):
            campo = "rol" if cambia_rol else "sede_id"
            raise serializers.ValidationError(
                {campo: "Tiene entregas en curso: espera a que terminen o reasígnalas primero."}
            )

        attrs["_rol"], attrs["_sede"] = rol, sede
        return attrs

    @transaction.atomic
    def update(self, empleado, validated):
        from .repartidores import poner_no_disponible

        usuario = empleado.usuario
        rol_actual = rol_de(usuario)
        rol, sede = validated.pop("_rol"), validated.pop("_sede")
        activa = validated.pop("activa", None)
        validated.pop("rol", None)
        validated.pop("sede_id", None)

        sede_cambio = (sede.pk if sede else None) != empleado.sede_id
        empleado = super().update(empleado, validated)
        empleado.sede = sede
        empleado.save(update_fields=["sede"])

        if rol != rol_actual:
            roles = {r.lower() for r in ROLES_PERSONAL}
            usuario.groups.remove(*[g for g in usuario.groups.all() if g.name.lower() in roles])
            usuario.groups.add(Group.objects.get_or_create(name=rol.lower())[0])
            usuario.is_staff = rol == ADMINISTRADOR.upper()
            usuario.save(update_fields=["is_staff"])

        if rol == REPARTIDOR.upper():
            Repartidor.objects.get_or_create(empleado=empleado, defaults={"disponible": False})
        if rol_actual == REPARTIDOR.upper() and (rol != rol_actual or sede_cambio):
            poner_no_disponible(usuario)

        if activa is not None and activa != usuario.is_active:
            usuario.is_active = activa
            usuario.save(update_fields=["is_active"])
            if not activa and rol == REPARTIDOR.upper():
                poner_no_disponible(usuario)

        usuario.refresh_from_db()
        return empleado


@extend_schema(request=EmpleadoEdicionSerializer, responses={200: EmpleadoEdicionSerializer})
class EmpleadoDetalleView(generics.RetrieveUpdateAPIView):
    """HU-80: el administrador consulta, edita y reactiva una cuenta del personal."""

    queryset = Empleado.objects.select_related("usuario", "sede")
    serializer_class = EmpleadoEdicionSerializer
    permission_classes = [rol_requerido(ADMINISTRADOR)]
    http_method_names = ["get", "put", "patch", "head", "options"]