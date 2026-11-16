from rest_framework import serializers

from sedes.models import Sede
from usuarios.roles import ADMINISTRADOR, obtener_rol, obtener_sede

from django.db import transaction

from menu.models import Producto

from . import combos, cupos
from .models import Combo, ComboProducto, ComboSede, Promocion, TipoDescuento


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
    usos_hoy = serializers.SerializerMethodField()
    cupo_restante = serializers.SerializerMethodField()

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
            "cupo_max_diario",
            "usos_hoy",
            "cupo_restante",
            "estado",
            "utilizable",
        ]
        extra_kwargs = {"cupo_max_diario": {"required": False, "allow_null": True}}

    def get_usos_hoy(self, promocion):
        return cupos.usos_hoy(promocion)

    def get_cupo_restante(self, promocion):
        # None = sin límite.
        return cupos.cupo_restante(promocion)

    def validate_cupo_max_diario(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "El cupo diario debe ser un entero mayor que 0 (vacío = sin límite)."
            )
        return value

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


class ComboProductoSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.select_related("categoria"))
    cantidad = serializers.IntegerField(min_value=1, max_value=50)


class ComboSerializer(serializers.ModelSerializer):
    """HU-85: combo de una sede (productos agrupados a un precio especial).

    - El operador crea en SU sede; el administrador debe elegirla.
    - El precio debe ser menor que la suma de los productos sueltos.
    - Disponibilidad y motivo se calculan al leer (producto desactivado o agotado).
    - Editar aplica a compras futuras: los pedidos ya hechos conservan su precio.
    """

    sede = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.filter(activa=True), required=False, write_only=True
    )
    sede_id = serializers.SerializerMethodField()
    sede_nombre = serializers.SerializerMethodField()
    productos = ComboProductoSerializer(many=True, write_only=True, required=False)
    productos_detalle = serializers.SerializerMethodField()
    suma_individual = serializers.SerializerMethodField()
    ahorro = serializers.SerializerMethodField()
    disponible = serializers.SerializerMethodField()
    motivo_no_disponible = serializers.SerializerMethodField()
    cupo_max_diario = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    usos_hoy = serializers.SerializerMethodField()
    cupo_restante = serializers.SerializerMethodField()

    class Meta:
        model = Combo
        fields = [
            "id", "sede", "sede_id", "sede_nombre", "nombre", "descripcion", "condicion",
            "precio", "fecha_inicio", "fecha_vencimiento", "activo",
            "productos", "productos_detalle", "suma_individual", "ahorro",
            "disponible", "motivo_no_disponible",
            "cupo_max_diario", "usos_hoy", "cupo_restante",
        ]

    # --- lectura (se calcula una vez por combo y se reutiliza) ---

    def _combo_sede(self, combo):
        sede_operador = self.context.get("sede")
        enlaces = list(combo.sedes_disponibles.all())
        if sede_operador is not None:
            enlaces = [e for e in enlaces if e.sede_id == sede_operador.pk] or enlaces
        return enlaces[0] if enlaces else None

    def _estado(self, combo):
        cache = self.context.setdefault("_cache_combos", {})
        if combo.pk not in cache:
            cs = self._combo_sede(combo)
            detalle = combos.detalle_productos(combo, cs.sede) if cs else []
            disponible, motivo = (
                combos.disponibilidad(combo, cs, detalle) if cs else (False, "Sin sede.")
            )
            cache[combo.pk] = (cs, detalle, disponible, motivo)
        return cache[combo.pk]

    def get_sede_id(self, combo):
        return self._estado(combo)[0].sede_id

    def get_sede_nombre(self, combo):
        return self._estado(combo)[0].sede.nombre

    def get_productos_detalle(self, combo):
        return [
            {**linea, "precio_base": str(linea["precio_base"])} for linea in self._estado(combo)[1]
        ]

    def get_suma_individual(self, combo):
        return str(sum((l["precio_base"] * l["cantidad"] for l in self._estado(combo)[1]), combos.CERO))

    def get_ahorro(self, combo):
        suma = sum((l["precio_base"] * l["cantidad"] for l in self._estado(combo)[1]), combos.CERO)
        return str(suma - combo.precio)

    def get_disponible(self, combo):
        return self._estado(combo)[2]

    def get_motivo_no_disponible(self, combo):
        return self._estado(combo)[3]

    def get_usos_hoy(self, combo):
        return cupos.usos_hoy(self._estado(combo)[0])

    def get_cupo_restante(self, combo):
        return cupos.cupo_restante(self._estado(combo)[0])

    def to_representation(self, instance):
        datos = super().to_representation(instance)
        cs = self._estado(instance)[0]
        datos["cupo_max_diario"] = cs.cupo_max_diario
        return datos

    # --- validación ---

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio del combo debe ser mayor que 0.")
        return value

    def validate_cupo_max_diario(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "El cupo diario debe ser un entero mayor que 0 (vacío = sin límite)."
            )
        return value

    def validate_productos(self, value):
        ids = [linea["producto"].pk for linea in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Hay productos repetidos en el combo.")
        for linea in value:
            producto = linea["producto"]
            if not producto.activo or not producto.categoria.activa:
                raise serializers.ValidationError(f"«{producto.nombre}» está desactivado.")
        if sum(linea["cantidad"] for linea in value) < 2:
            raise serializers.ValidationError("Un combo agrupa al menos 2 productos.")
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
                    raise serializers.ValidationError({"sede": "Elige la sede del combo."})
            else:
                sede_operador = obtener_sede(usuario)
                if sede_operador is None:
                    raise serializers.ValidationError({"sede": "Tu cuenta no tiene una sede asignada."})
                data["sede"] = sede_operador
            if "productos" not in data:
                raise serializers.ValidationError({"productos": "Agrega los productos del combo."})
            sede = data["sede"]
        else:
            if "sede" in data and data["sede"].pk != self._combo_sede(instancia).sede_id:
                raise serializers.ValidationError({"sede": "No se puede mover un combo a otra sede."})
            sede = self._combo_sede(instancia).sede
            if instancia.sedes_disponibles.exclude(sede=sede).exists():
                raise serializers.ValidationError(
                    "Este combo también está en otras sedes y no se puede editar desde aquí."
                )

        # Vigencia
        inicio, fin = actual("fecha_inicio"), actual("fecha_vencimiento")
        if inicio and fin and fin < inicio:
            raise serializers.ValidationError(
                {"fecha_vencimiento": "La fecha de fin no puede ser anterior a la de inicio."}
            )

        # Precio especial: menor que la suma de los productos sueltos
        if "productos" in data:
            lineas = [(l["producto"], l["cantidad"]) for l in data["productos"]]
        else:
            lineas = [
                (i.producto, i.cantidad) for i in instancia.productos_incluidos.select_related("producto")
            ]
        precio, suma = actual("precio"), combos.suma_individual(lineas)
        if precio is not None and precio >= suma:
            raise serializers.ValidationError({
                "precio": (
                    f"El precio del combo (${precio:,.0f}) debe ser menor que el total individual "
                    f"de sus productos (${suma:,.0f})."
                )
            })

        # Nombre único dentro de la sede
        nombre = actual("nombre")
        if nombre:
            repetidos = Combo.objects.filter(
                sedes_disponibles__sede=sede, nombre__iexact=nombre.strip()
            )
            if instancia:
                repetidos = repetidos.exclude(pk=instancia.pk)
            if repetidos.exists():
                raise serializers.ValidationError(
                    {"nombre": "Ya existe un combo con este nombre en la sede."}
                )
        return data

    # --- escritura ---

    @staticmethod
    def _guardar_productos(combo, lineas):
        combo.productos_incluidos.all().delete()
        ComboProducto.objects.bulk_create(
            [ComboProducto(combo=combo, producto=l["producto"], cantidad=l["cantidad"]) for l in lineas]
        )

    @transaction.atomic
    def create(self, validated_data):
        sede = validated_data.pop("sede")
        lineas = validated_data.pop("productos")
        cupo = validated_data.pop("cupo_max_diario", None)
        combo = Combo.objects.create(**validated_data)
        self._guardar_productos(combo, lineas)
        ComboSede.objects.create(combo=combo, sede=sede, cupo_max_diario=cupo)
        return combo

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop("sede", None)
        lineas = validated_data.pop("productos", None)
        tiene_cupo = "cupo_max_diario" in validated_data
        cupo = validated_data.pop("cupo_max_diario", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save()
        if lineas is not None:
            self._guardar_productos(instance, lineas)
        enlace = instance.sedes_disponibles.get()
        cambios = []
        if tiene_cupo:
            enlace.cupo_max_diario = cupo
            cambios.append("cupo_max_diario")
        if "activo" in validated_data:
            enlace.activo = validated_data["activo"]
            cambios.append("activo")
        if cambios:
            enlace.save(update_fields=cambios)
        return instance