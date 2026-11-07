from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .serializers import SedeSerializer, CiudadSerializer
from rest_framework import viewsets
from .models import Ciudad, Sede, HorarioSede, Feriado
from .serializers import HorarioSedeSerializer, FeriadoSerializer

# Permiso personalizado
class EsAdministradorPermission(permissions.BasePermission):
    """Permite mutaciones (POST, PUT, DELETE) solo a usuarios autenticados como Administrador."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        rol = getattr(request.user, 'rol', None)
        return request.user.is_staff or rol == 'ADMINISTRADOR'


# ViewSet de Sedes
class SedeViewSet(viewsets.ModelViewSet):
    queryset = Sede.objects.select_related('ciudad').all()
    serializer_class = SedeSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [EsAdministradorPermission()]

    def get_queryset(self):
        queryset = super().get_queryset()
        activa_param = self.request.query_params.get('activa', None)
        if activa_param is not None:
            es_activa = activa_param.lower() in ['true', '1']
            queryset = queryset.filter(activa=es_activa)
        return queryset

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        nuevo_estado_activo = request.data.get('activa', instance.activa)
        confirmar_desactivacion = request.data.get('confirmar_desactivacion', False)

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


# ViewSet de Horarios (HU-82)
class HorarioSedeViewSet(viewsets.ModelViewSet):
    queryset = HorarioSede.objects.all()
    serializer_class = HorarioSedeSerializer
    permission_classes = [EsAdministradorPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get('sede', None)
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)
        return queryset


# ViewSet de Feriados (HU-82)
class FeriadoViewSet(viewsets.ModelViewSet):
    queryset = Feriado.objects.all()
    serializer_class = FeriadoSerializer
    permission_classes = [EsAdministradorPermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        sede_id = self.request.query_params.get('sede', None)
        if sede_id:
            queryset = queryset.filter(sede_id=sede_id)
        return queryset

class CiudadViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ciudad.objects.all()
    serializer_class = CiudadSerializer
    permission_classes = [permissions.AllowAny]