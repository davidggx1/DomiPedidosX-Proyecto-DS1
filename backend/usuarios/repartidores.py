"""
HU-41 · Disponibilidad del repartidor.

Vive en un módulo aparte de views.py y serializers.py para no chocar con los
cambios de login, registro y direcciones que se hacen en esos archivos.
"""
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import NotFound

from pedidos.asignacion import ESTADOS_EN_CURSO

from .models import Repartidor
from .permissions import EsRepartidor, filtrar_por_sede, rol_requerido
from .roles import ADMINISTRADOR, OPERADOR


def poner_no_disponible(usuario):
    """Al iniciar sesión, el repartidor arranca "No disponible" (HU-41, criterio 4)."""
    Repartidor.objects.filter(empleado__usuario=usuario).update(disponible=False)


class DisponibilidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repartidor
        fields = ["disponible"]
        extra_kwargs = {
            "disponible": {
                "required": True,
                "error_messages": {
                    "required": "Indica si estás disponible.",
                    "invalid": "El valor debe ser verdadero o falso.",
                },
            }
        }
    
    def validate(self, attrs):
        # En un PATCH los campos son opcionales; aquí "disponible" es obligatorio.
        if "disponible" not in attrs:
            raise serializers.ValidationError({"disponible": "Indica si estás disponible."})
        return attrs


class RepartidorSerializer(serializers.ModelSerializer):
    """Lo que ve el operador de cada repartidor de su sede."""

    nombres = serializers.CharField(source="empleado.nombres", read_only=True)
    apellidos = serializers.CharField(source="empleado.apellidos", read_only=True)
    celular = serializers.CharField(source="empleado.celular", read_only=True)
    sede_id = serializers.IntegerField(source="empleado.sede_id", read_only=True)
    pedidos_activos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Repartidor
        fields = ["id", "nombres", "apellidos", "celular", "sede_id", "disponible", "pedidos_activos"]


class MiDisponibilidadView(generics.RetrieveUpdateAPIView):
    """
    GET / PATCH /api/usuarios/repartidor/disponibilidad/

    El repartidor consulta o cambia su propio estado de trabajo.
    Pasar a "No disponible" no le quita los pedidos que ya tiene asignados:
    debe terminar esas entregas (criterio 3).
    """

    serializer_class = DisponibilidadSerializer
    permission_classes = [EsRepartidor]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        perfil = Repartidor.objects.filter(empleado__usuario=self.request.user).first()
        if perfil is None:
            raise NotFound("Tu cuenta no tiene un perfil de repartidor.")
        return perfil


@extend_schema(responses=RepartidorSerializer(many=True))
class RepartidoresView(generics.ListAPIView):
    """
    GET /api/usuarios/repartidores/?disponible=true

    Repartidores activos con su disponibilidad, para el panel del operador
    (criterio 1). El operador ve solo los de su sede; el administrador, todos.
    """

    serializer_class = RepartidorSerializer
    permission_classes = [rol_requerido(OPERADOR, ADMINISTRADOR)]
    pagination_class = None

    def get_queryset(self):
        en_curso = Q(pedidos_asignados__estado__in=ESTADOS_EN_CURSO)
        repartidores = (
            Repartidor.objects.filter(empleado__usuario__is_active=True)
            .select_related("empleado")
            .annotate(pedidos_activos=Count("pedidos_asignados", filter=en_curso))
            .order_by("empleado__nombres", "empleado__apellidos")
        )
        disponible = self.request.query_params.get("disponible")
        if disponible is not None:
            repartidores = repartidores.filter(disponible=disponible.lower() in ("true", "1"))
        return filtrar_por_sede(repartidores, self.request.user, campo="empleado__sede")
