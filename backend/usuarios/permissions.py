from functools import reduce

from rest_framework.permissions import BasePermission

from .roles import (
    ADMINISTRADOR,
    COCINA,
    OPERADOR,
    REPARTIDOR,
    ROLES_PERSONAL,
    obtener_rol,
    obtener_sede,
)


class PermisoPorRol(BasePermission):
    """Base: define `roles` en la subclase. Autenticado y con alguno de esos roles."""

    roles = ()
    message = "No tienes permiso para acceder a esta función."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and obtener_rol(usuario) in self.roles
        )


class EsAdministrador(PermisoPorRol):
    roles = (ADMINISTRADOR,)


class EsOperador(PermisoPorRol):
    roles = (OPERADOR,)


class EsCocina(PermisoPorRol):
    roles = (COCINA,)


class EsRepartidor(PermisoPorRol):
    roles = (REPARTIDOR,)


class EsPersonal(PermisoPorRol):
    """Cualquier rol del personal (excluye a los clientes)."""

    roles = ROLES_PERSONAL


class PerteneceALaSede(BasePermission):
    """A nivel de objeto: el administrador accede a todo; el resto, solo a objetos
    de su sede. La vista puede definir `campo_sede` (por defecto "sede"; admite
    rutas con puntos, p. ej. "pedido.sede")."""

    message = "Este recurso pertenece a otra sede."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and obtener_rol(usuario) in ROLES_PERSONAL
        )

    def has_object_permission(self, request, view, obj):
        usuario = request.user
        if obtener_rol(usuario) == ADMINISTRADOR:
            return True
        sede_usuario = obtener_sede(usuario)
        if sede_usuario is None:
            return False
        campo = getattr(view, "campo_sede", "sede")
        sede_objeto = reduce(getattr, campo.split("."), obj)
        return getattr(sede_objeto, "pk", sede_objeto) == sede_usuario.pk


def rol_requerido(*roles):
    """Atajo: rol_requerido(OPERADOR, COCINA) devuelve una clase de permiso."""
    return type("PermisoRol", (PermisoPorRol,), {"roles": roles})


def filtrar_por_sede(queryset, usuario, campo="sede"):
    """Para listados: el administrador ve todo; el resto solo lo de su sede."""
    if obtener_rol(usuario) == ADMINISTRADOR:
        return queryset
    return queryset.filter(**{campo: obtener_sede(usuario)})


class EsCliente(BasePermission):
    """Autenticado y con perfil de cliente (no aplica a empleados)."""

    message = "Esta función es solo para clientes."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario and usuario.is_authenticated and hasattr(usuario, "cliente"))
