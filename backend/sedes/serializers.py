from rest_framework import serializers
from .models import Sede, Ciudad, HorarioSede, Feriado, CapacidadSede

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

class CapacidadSedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacidadSede
        fields = [
            'id',
            'sede',
            'hora_inicio',
            'hora_fin',
            'dias_semana',
            'max_pedidos_simultaneos',
            'umbral_alerta',
        ]

    def validate_max_pedidos_simultaneos(self, value):
        if value < 1:
            raise serializers.ValidationError("La capacidad máxima de pedidos debe ser al menos 1.")
        return value

    def validate(self, data):
        sede = data.get('sede', getattr(self.instance, 'sede', None))
        inicio = data.get('hora_inicio', getattr(self.instance, 'hora_inicio', None))
        fin = data.get('hora_fin', getattr(self.instance, 'hora_fin', None))
        dias = data.get('dias_semana', getattr(self.instance, 'dias_semana', ''))

        if inicio and fin and inicio >= fin:
            raise serializers.ValidationError({
                "hora_fin": "La hora de inicio debe ser estrictamente anterior a la hora de fin."
            })

        # Validación de Solapamiento Horario por días de la semana
        if sede and inicio and fin and dias:
            dias_lista = [d.strip().lower() for d in dias.split(',') if d.strip()]
            capacidades_existentes = CapacidadSede.objects.filter(sede=sede)
            if self.instance:
                capacidades_existentes = capacidades_existentes.exclude(pk=self.instance.pk)

            for cap in capacidades_existentes:
                cap_dias = [d.strip().lower() for d in cap.dias_semana.split(',') if d.strip()]
                # Verificar intersección de días
                if any(d in cap_dias for d in dias_lista):
                    # Verificar solapamiento de horario: max(inicio1, inicio2) < min(fin1, fin2)
                    if max(inicio, cap.hora_inicio) < min(fin, cap.hora_fin):
                        raise serializers.ValidationError(
                            f"La franja {inicio.strftime('%H:%M')} - {fin.strftime('%H:%M')} se solapa "
                            f"con una configuración existente ({cap.hora_inicio.strftime('%H:%M')} - {cap.hora_fin.strftime('%H:%M')})."
                        )

        return data