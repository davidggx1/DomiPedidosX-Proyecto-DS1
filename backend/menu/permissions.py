from rest_framework import permissions

# Groups that can manage the menu (same names as seed_datos)
ROLES_GESTION_MENU = {"operador", "administrador"}


class EsPersonalDeMenu(permissions.BasePermission):
    """Only operador and administrador can manage the menu"""

    def has_permission(self, request, view):
        usuario = request.user
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_staff:
            return True
        return usuario.groups.filter(name__in=ROLES_GESTION_MENU).exists()
