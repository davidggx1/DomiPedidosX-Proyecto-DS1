from rest_framework import serializers
from .models import Sede, Ciudad


class SedeSerializer(serializers.ModelSerializer):
    ciudad_nombre = serializers.ReadOnlyField(source='ciudad.nombre')
    tiene_pedidos_pendientes = serializers.SerializerMethodField()

    class Meta:
        model = Sede
        fields = [
            'id',
            'ciudad',
            'ciudad_nombre',
            'nombre',
            'direccion',
            'activa',
            'latitud',
            'longitud',
            'barrio',
            'telefono',
            'correo',
            'fecha_registro',
            'tiene_pedidos_pendientes',
        ]

    def get_tiene_pedidos_pendientes(self, obj):
        # Chequeo preparado para cuando la app de 'pedidos' se integre en el Sprint 2
        # return obj.pedidos.filter(estado__in=['pendiente', 'recibido', 'en_preparacion']).exists()
        return False

    def validate_nombre(self, value):
        nombre_limpio = value.strip()
        instance = getattr(self, 'instance', None)
        query = Sede.objects.filter(nombre__iexact=nombre_limpio)

        if instance:
            query = query.exclude(pk=instance.pk)

        if query.exists():
            raise serializers.ValidationError("Ya existe una sede registrada con este nombre.")
        return nombre_limpio