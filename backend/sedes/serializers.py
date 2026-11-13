import unicodedata

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .geometria import envolvente, normalizar_poligono, traslapan
from .models import Sede, Ciudad, HorarioSede, Feriado, CapacidadSede, ZonaCobertura, DiaSemana


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")

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

    def get_tiene_pedidos_pendientes(self, obj) -> bool:
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

    def validate_dias_semana(self, value):
        """Acepta tildes, mayúsculas y espacios ("Miércoles, SÁBADO") y guarda
        los valores de DiaSemana ("miercoles,sabado"), que es lo que busca la
        franja actual. Rechaza días que no existen (SCRUM-121)."""
        validos = [dia.value for dia in DiaSemana]
        dias = []
        for parte in value.split(","):
            dia = _sin_tildes(parte.strip().lower())
            if not dia:
                continue
            if dia not in validos:
                raise serializers.ValidationError(
                    f'"{parte.strip()}" no es un día válido. Usa: {", ".join(validos)}.'
                )
            if dia not in dias:
                dias.append(dia)
        if not dias:
            raise serializers.ValidationError("Indica al menos un día de la semana.")
        return ",".join(dias)

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


class ZonaCoberturaSerializer(serializers.ModelSerializer):
    """Zona de cobertura de una sede, por radio o por polígono.

    - Por radio: enviar `radio` (km, > 0), `centro_latitud` y `centro_longitud`.
    - Por polígono: enviar `poligono_vertices` como [[lat, lon], ...] (mínimo 3 puntos;
      el cierre puede repetirse o no). `centro_*` y `radio` se calculan solos.
    - Dos zonas activas de la misma sede no pueden traslaparse.
    """

    tipo = serializers.SerializerMethodField()

    class Meta:
        model = ZonaCobertura
        fields = [
            "id", "sede", "nombre", "tipo", "radio", "centro_latitud", "centro_longitud",
            "poligono_vertices", "tarifa_domicilio", "tiempo_estimado", "pedido_minimo",
            "activo",
        ]
        extra_kwargs = {
            "radio": {"required": False},
            "centro_latitud": {"required": False},
            "centro_longitud": {"required": False},
        }

    @extend_schema_field(serializers.ChoiceField(choices=["radio", "poligono"]))
    def get_tipo(self, obj):
        return "poligono" if obj.poligono_vertices else "radio"

    def validate_tarifa_domicilio(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("La tarifa no puede ser negativa.")
        return value

    def validate_pedido_minimo(self, value):
        if value < 0:
            raise serializers.ValidationError("El pedido mínimo no puede ser negativo.")
        return value

    def validate_tiempo_estimado(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("El tiempo estimado debe ser mayor que 0 minutos.")
        return value

    def validate(self, data):
        instancia = self.instance

        def actual(campo, por_defecto=None):
            return data[campo] if campo in data else getattr(instancia, campo, por_defecto)

        sede = actual("sede")
        if instancia and sede != instancia.sede:
            raise serializers.ValidationError({"sede": "No se puede mover una zona a otra sede."})

        vertices = actual("poligono_vertices")
        if vertices:
            try:
                vertices = normalizar_poligono(vertices)
            except ValueError as error:
                raise serializers.ValidationError({"poligono_vertices": str(error)})
            centro_lat, centro_lon, radio = envolvente(vertices)
        else:
            vertices = None
            centro_lat = actual("centro_latitud")
            centro_lon = actual("centro_longitud")
            radio = actual("radio")
            for campo, valor in (
                ("radio", radio), ("centro_latitud", centro_lat), ("centro_longitud", centro_lon)
            ):
                if valor is None:
                    raise serializers.ValidationError(
                        {campo: "Obligatorio en una zona por radio (o envía poligono_vertices)."}
                    )
            if radio <= 0:
                raise serializers.ValidationError({"radio": "El radio debe ser mayor que 0 km."})
            if not (-90 <= centro_lat <= 90):
                raise serializers.ValidationError({"centro_latitud": "Latitud fuera de rango."})
            if not (-180 <= centro_lon <= 180):
                raise serializers.ValidationError({"centro_longitud": "Longitud fuera de rango."})

        data["poligono_vertices"] = vertices
        data["centro_latitud"], data["centro_longitud"], data["radio"] = (
            centro_lat, centro_lon, radio
        )


        # HU-56: sin tarifa y tiempo, la zona no puede estar activa.
        if actual("tarifa_domicilio") is None or actual("tiempo_estimado") is None:
            if data.get("activo") is True:
                raise serializers.ValidationError(
                    {"activo": "Para activar la zona define la tarifa y el tiempo estimado."}
                )
            data["activo"] = False

        # Solo las zonas activas operan, así que solo ellas se comparan.
        if actual("activo", True):
            nueva = (centro_lat, centro_lon, radio, vertices)
            otras = ZonaCobertura.objects.filter(sede=sede, activo=True)
            if instancia:
                otras = otras.exclude(pk=instancia.pk)
            for otra in otras:
                existente = (
                    otra.centro_latitud, otra.centro_longitud, otra.radio, otra.poligono_vertices
                )
                if traslapan(nueva, existente):
                    raise serializers.ValidationError(
                        f"La zona se traslapa con «{otra.nombre}», que ya está activa en esta sede."
                    )
        return data