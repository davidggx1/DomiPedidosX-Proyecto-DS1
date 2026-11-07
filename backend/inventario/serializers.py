"""
HU-14 · Existencias por sede (productos e ingredientes).

Reglas:
- El operador solo registra/edita en su sede; el administrador debe indicar la sede.
- No se repite el mismo producto/ingrediente en una sede.
- Producto/ingrediente y sede no se pueden cambiar una vez creado el registro.
"""
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from menu.disponibilidad import sedes_que_gestiona
from menu.models import Insumo, Producto
from sedes.models import Sede

from .models import InventarioInsumo, InventarioProducto

ENTERO_MAX = 2_147_483_647


def _mensajes_entero(nombre):
    return {
        "required": f"{nombre} es obligatorio.",
        "null": f"{nombre} es obligatorio.",
        "invalid": f"{nombre} debe ser un número entero.",
        "min_value": f"{nombre} no puede ser negativo.",
        "max_value": f"{nombre} es demasiado grande.",
        "max_string_length": f"{nombre} es demasiado grande.",
    }


def _mensajes_decimal(nombre):
    return {
        "required": f"{nombre} es obligatorio.",
        "null": f"{nombre} es obligatorio.",
        "invalid": f"{nombre} debe ser un número válido.",
        "min_value": f"{nombre} no puede ser negativo.",
        "max_digits": f"{nombre} es demasiado grande.",
        "max_whole_digits": f"{nombre} es demasiado grande.",
        "max_decimal_places": f"{nombre} admite máximo 3 decimales.",
        "max_string_length": f"{nombre} es demasiado grande.",
    }


class InventarioBaseSerializer(serializers.ModelSerializer):
    """Lógica común. Las subclases definen `campo_item` ('producto' o 'insumo')."""

    campo_item = None
    etiqueta_item = None

    sede = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.filter(activa=True),
        required=False,
        error_messages={
            "null": "Indica la sede.",
            "does_not_exist": "La sede no existe o está inactiva.",
            "incorrect_type": "La sede debe ser un id numérico.",
        },
    )
    sede_nombre = serializers.CharField(source="sede.nombre", read_only=True)

    def validate(self, attrs):
        item = self.campo_item
        if self.instance is not None:
            return self._validar_edicion(attrs)

        if not attrs[item].activo:
            raise serializers.ValidationError(
                {item: f"El {self.etiqueta_item} no existe o está inactivo."}
            )

        gestionables = sedes_que_gestiona(self.context["request"].user)
        sede = attrs.get("sede")
        if gestionables is None:
            if sede is None:
                raise serializers.ValidationError({"sede": "Indica la sede."})
        else:
            if not gestionables or (sede is not None and sede.id not in gestionables):
                raise PermissionDenied("Solo puedes registrar existencias en tu sede.")
            if sede is None:
                sede = Sede.objects.get(pk=next(iter(gestionables)))
                attrs["sede"] = sede

        modelo = self.Meta.model
        if modelo.objects.filter(sede=sede, **{item: attrs[item]}).exists():
            raise serializers.ValidationError(
                {item: f"Esta sede ya tiene existencias registradas de este {self.etiqueta_item}."}
            )
        return attrs

    def _validar_edicion(self, attrs):
        item = self.campo_item
        errores = {}
        if item in attrs and attrs[item] != getattr(self.instance, item):
            errores[item] = f"No se puede cambiar el {self.etiqueta_item} de un registro de inventario."
        if "sede" in attrs and attrs["sede"] != self.instance.sede:
            errores["sede"] = "No se puede cambiar la sede de un registro de inventario."
        if errores:
            raise serializers.ValidationError(errores)
        return attrs


class InventarioProductoSerializer(InventarioBaseSerializer):
    campo_item = "producto"
    etiqueta_item = "producto"

    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(),
        error_messages={
            "required": "Selecciona el producto.",
            "null": "Selecciona el producto.",
            "does_not_exist": "El producto no existe o está inactivo.",
            "incorrect_type": "El producto debe ser un id numérico.",
        },
    )
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    categoria_nombre = serializers.CharField(source="producto.categoria.nombre", read_only=True)
    stock_actual = serializers.IntegerField(
        min_value=0, max_value=ENTERO_MAX, error_messages=_mensajes_entero("El stock actual")
    )
    stock_minimo = serializers.IntegerField(
        min_value=0,
        max_value=ENTERO_MAX,
        required=False,
        default=0,
        error_messages=_mensajes_entero("El stock mínimo"),
    )

    class Meta:
        model = InventarioProducto
        fields = [
            "id", "sede", "sede_nombre", "producto", "producto_nombre", "categoria_nombre",
            "stock_actual", "stock_minimo", "disponible", "demanda_diaria",
            "fecha_actualizacion",
        ]
        read_only_fields = ["disponible", "demanda_diaria", "fecha_actualizacion"]
        # El UniqueConstraint (sede, item) haría obligatoria la sede; la unicidad se valida en validate().
        validators = []


class InventarioInsumoSerializer(InventarioBaseSerializer):
    campo_item = "insumo"
    etiqueta_item = "ingrediente"

    insumo = serializers.PrimaryKeyRelatedField(
        queryset=Insumo.objects.all(),
        error_messages={
            "required": "Selecciona el ingrediente.",
            "null": "Selecciona el ingrediente.",
            "does_not_exist": "El ingrediente no existe o está inactivo.",
            "incorrect_type": "El ingrediente debe ser un id numérico.",
        },
    )
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="insumo.unidad_medida", read_only=True)
    stock_actual = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=0,
        error_messages=_mensajes_decimal("El stock actual"),
    )
    stock_minimo = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=0, required=False, default=0,
        error_messages=_mensajes_decimal("El stock mínimo"),
    )

    class Meta:
        model = InventarioInsumo
        fields = [
            "id", "sede", "sede_nombre", "insumo", "insumo_nombre", "unidad_medida",
            "stock_actual", "stock_minimo", "disponible", "demanda_diaria",
            "fecha_actualizacion",
        ]
        read_only_fields = ["disponible", "demanda_diaria", "fecha_actualizacion"]
        # El UniqueConstraint (sede, item) haría obligatoria la sede; la unicidad se valida en validate().
        validators = []
