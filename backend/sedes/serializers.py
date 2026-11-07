from rest_framework import serializers
from .models import Sede, Ciudad, HorarioSede, Feriado

class CiudadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ciudad
        fields = ['id', 'nombre']

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

class HorarioSedeSerializer(serializers.ModelSerializer):
    dia_semana_display = serializers.CharField(source='get_dia_semana_display', read_only=True)

    class Meta:
        model = HorarioSede
        fields = [
            'id',
            'sede',
            'dia_semana',
            'dia_semana_display',
            'hora_apertura',
            'hora_cierre',
        ]

    def validate(self, data):
        # Valida la restricción a nivel de serializador: hora_apertura < hora_cierre
        apertura = data.get('hora_apertura', getattr(self.instance, 'hora_apertura', None))
        cierre = data.get('hora_cierre', getattr(self.instance, 'hora_cierre', None))

        if apertura and cierre and apertura >= cierre:
            raise serializers.ValidationError(
                "La hora de apertura debe ser anterior a la hora de cierre."
            )
        return data


class FeriadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feriado
        fields = [
            'id',
            'sede',
            'fecha',
            'descripcion',
            'cerrado',
            'hora_apertura',
            'hora_cierre',
        ]

    def validate(self, data):
        cerrado = data.get('cerrado', getattr(self.instance, 'cerrado', True))
        apertura = data.get('hora_apertura', getattr(self.instance, 'hora_apertura', None))
        cierre = data.get('hora_cierre', getattr(self.instance, 'hora_cierre', None))

        # Si no está cerrado todo el día, requiere horas de atención válidas
        if not cerrado:
            if not apertura or not cierre:
                raise serializers.ValidationError(
                    "Si el festivo no es cerrado, debe especificar hora de apertura y cierre."
                )
            if apertura >= cierre:
                raise serializers.ValidationError(
                    "La hora de apertura debe ser anterior a la hora de cierre en el horario especial."
                )
        return data