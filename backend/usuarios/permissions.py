from rest_framework.permissions import BasePermission

from .roles import obtener_rol, obtener_sede, ADMINISTRADOR


def rol_requerido(*roles):
    """Permiso que solo deja pasar a usuarios con alguno de los roles dados."""

    class PermisoRol(BasePermission):
        message = "No tienes permiso para acceder a esta función."

        def has_permission(self, request, view):
            usuario = request.user
            return bool(
                usuario and usuario.is_authenticated and obtener_rol(usuario) in roles
            )

    return PermisoRol


def filtrar_por_sede(queryset, usuario, campo="sede"):
    """El administrador ve todo; el resto solo lo de su sede."""
    if obtener_rol(usuario) == ADMINISTRADOR:
        return queryset
    return queryset.filter(**{campo: obtener_sede(usuario)})