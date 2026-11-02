from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Sede
from .serializers import SedeSerializer


class EsAdministradorPermission(permissions.BasePermission):
    """Permite mutaciones (POST, PUT, DELETE) solo a usuarios autenticados como Administrador."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Soporta is_staff de Django o campo personalizado 'rol'
        rol = getattr(request.user, 'rol', None)
        return request.user.is_staff or rol == 'ADMINISTRADOR'


class SedeViewSet(viewsets.ModelViewSet):
    queryset = Sede.objects.select_related('ciudad').all()
    serializer_class = SedeSerializer

    def get_permissions(self):
        # El catálogo permite GET libre (o a clientes), pero POST/PUT/DELETE exige rol Administrador
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [EsAdministradorPermission()]

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtro de activas e inactivas por query parameter: /api/sedes/?activa=true
        activa_param = self.request.query_params.get('activa', None)
        if activa_param is not None:
            es_activa = activa_param.lower() in ['true', '1']
            queryset = queryset.filter(activa=es_activa)
        return queryset

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        nuevo_estado_activo = request.data.get('activa', instance.activa)
        confirmar_desactivacion = request.data.get('confirmar_desactivacion', False)

        # Advertencia al desactivar si existen pedidos pendientes
        if instance.activa and not nuevo_estado_activo:
            serializer = self.get_serializer(instance)
            if serializer.data['tiene_pedidos_pendientes'] and not confirmar_desactivacion:
                return Response(
                    {
                        "warning": True,
                        "message": (
                            f"La sede '{instance.nombre}' tiene pedidos pendientes por entregar. "
                            "¿Desea confirmar la desactivación?"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().update(request, *args, **kwargs)