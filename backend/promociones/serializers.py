from rest_framework import serializers

from sedes.models import Sede
from usuarios.roles import ADMINISTRADOR, obtener_rol, obtener_sede

from .models import Promocion, TipoDescuento


class PromocionSerializer(serializers.ModelSerializer):
    """HU-84: promoción de una sede.

    - El operador siempre crea en SU sede; el administrador debe elegirla.
    - Una promoción no se mueve de sede.
    - Descuento mayor que 0; un porcentaje no puede pasar de 100.
    - La fecha de fin no puede ser anterior a la de inicio.
    """

    sede = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.filter(activa=True), required=False
    )
    sede_nombre = serializers.ReadOnlyField(source="sede.nombre")
    estado = serializers.SerializerMethodField()
    utilizable = serializers.SerializerMethodField()

    class Meta:
        model = Promocion
        fields = [
            "id",
            "sede",
            "sede_nombre",
            "nombre",
            "descripcion",
            "tipo_descuento",
            "valor",
            "fecha_inicio",
            "fecha_fin",
            "condiciones",
            "activa",
            "estado",
            "utilizable",
        ]

    def get_estado(self, promocion):
        return promocion.estado().value

    def get_utilizable(self, promocion):
        return promocion.utilizable()

    def validate_valor(self, value):
        if value <= 0:
            raise serializers.ValidationError("El descuento debe ser mayor que 0.")
        return value

    def validate(self, data):
        instancia = self.instance

        def actual(campo):
            return data[campo] if campo in data else getattr(instancia, campo, None)

        # Sede
        if instancia is None:
            usuario = self.context["request"].user
            if obtener_rol(usuario) == ADMINISTRADOR:
                if data.get("sede") is None:
                    raise serializers.ValidationError({"sede": "Elige la sede de la promoción."})
            else:
                sede_operador = obtener_sede(usuario)
                if sede_operador is None:
                    raise serializers.ValidationError(
                        {"sede": "Tu cuenta no tiene una sede asignada."}
                    )
                data["sede"] = sede_operador
        elif "sede" in data and data["sede"] != instancia.sede:
            raise serializers.ValidationError(
                {"sede": "No se puede mover una promoción a otra sede."}
            )
        sede = data.get("sede") or instancia.sede

        # Vigencia
        inicio, fin = actual("fecha_inicio"), actual("fecha_fin")
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError(
                {"fecha_fin": "La fecha de fin no puede ser anterior a la de inicio."}
            )

        # Descuento
        valor = actual("valor")
        if (
            actual("tipo_descuento") == TipoDescuento.PORCENTAJE
            and valor is not None
            and valor > 100
        ):
            raise serializers.ValidationError(
                {"valor": "El porcentaje no puede ser mayor que 100."}
            )

        # Nombre único dentro de la sede
        nombre = actual("nombre")
        if nombre:
            repetidas = Promocion.objects.filter(sede=sede, nombre__iexact=nombre.strip())
            if instancia:
                repetidas = repetidas.exclude(pk=instancia.pk)
            if repetidas.exists():
                raise serializers.ValidationError(
                    {"nombre": "Ya existe una promoción con este nombre en la sede."}
                )
        return data