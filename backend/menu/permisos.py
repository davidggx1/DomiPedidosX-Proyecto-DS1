"""
Permisos de la app menu.

Mientras la Tarea 3 (autenticación y permisos por rol) no esté integrada,
los roles se leen de los grupos de Django creados por `seed_datos`.
"""
from rest_framework.permissions import BasePermission

ROLES_GESTION_MENU = ("operador", "administrador")


class PuedeGestionarMenu(BasePermission):
    """Solo el operador de sede, el administrador o un superusuario gestionan el menú."""

    message = "Solo el operador de sede o el administrador pueden gestionar el menú."

    def has_permission(self, request, view):
        usuario = request.user
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_superuser:
            return True
        return usuario.groups.filter(name__in=ROLES_GESTION_MENU).exists()
