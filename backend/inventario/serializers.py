from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from menu.disponibilidad import sedes_que_gestiona
from menu.models import Insumo, Producto
from sedes.models import Sede

from .models import InventarioInsumo, InventarioProducto

# biggest value the integer column accepts
STOCK_MAXIMO = 2_147_483_647


def mensajes(campo, **extra):
    """Error messages in Spanish for a stock field"""
    base = {
        "required": f"{campo} es obligatorio.",
        "null": f"{campo} es obligatorio.",
        "invalid": f"{campo} debe ser un número válido.",
        "min_value": f"{campo} no puede ser negativo.",
        "max_value": f"{campo} es demasiado grande.",
    }
    base.update(extra)
    return base


class ValidacionInventarioMixin:
    """Sede rules shared by the product and ingredient stock serializers"""

    # name of the field that points to the stocked item ("producto" or "insumo")
    campo_item = None
    # how the item is called in the messages
    nombre_item = None

    def validate(self, attrs):
        if self.instance is not None:
            # sede and item are fixed once the record exists
            for campo in ("sede", self.campo_item):
                if campo in attrs and attrs[campo] != getattr(self.instance, campo):
                    raise serializers.ValidationError(
                        {campo: "No se puede cambiar. Elimina el registro y crea uno nuevo."}
                    )
            return attrs

        sede = self._sede_para_crear(attrs.get("sede"))
        attrs["sede"] = sede
        item = attrs[self.campo_item]
        if self.Meta.model.objects.filter(sede=sede, **{self.campo_item: item}).exists():
            raise serializers.ValidationError(
                {
                    self.campo_item: f"Este {self.nombre_item} ya tiene existencias registradas "
                    "en la sede. Edita el registro que ya existe."
                }
            )
        return attrs

    def _sede_para_crear(self, sede):
        gestionables = sedes_que_gestiona(self.context["request"].user)
        if gestionables is None:
            # administrador: has to say which sede
            if sede is None:
                raise serializers.ValidationError({"sede": "Indica la sede."})
            return sede
        if not gestionables:
            raise PermissionDenied("Tu cuenta no tiene una sede asignada.")
        if sede is None:
            # operador: defaults to its own sede
            return Sede.objects.get(pk=next(iter(gestionables)))
        if sede.id not in gestionables:
            raise PermissionDenied("Solo puedes gestionar el inventario de tu sede.")
        return sede


class InventarioProductoSerializer(ValidacionInventarioMixin, serializers.ModelSerializer):
    campo_item = "producto"
    nombre_item = "producto"

    sede = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.filter(activa=True),
        required=False,
        error_messages={
            "does_not_exist": "La sede no existe o está inactiva.",
            "incorrect_type": "La sede debe ser un id numérico.",
        },
    )
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(activo=True),
        error_messages={
            "required": "Selecciona el producto.",
            "null": "Selecciona el producto.",
            "does_not_exist": "El producto no existe o está inactivo.",
            "incorrect_type": "El producto debe ser un id numérico.",
        },
    )
    stock_actual = serializers.IntegerField(
        min_value=0,
        max_value=STOCK_MAXIMO,
        error_messages=mensajes(
            "El stock actual", invalid="El stock actual debe ser un número entero."
        ),
    )
    stock_minimo = serializers.IntegerField(
        min_value=0,
        max_value=STOCK_MAXIMO,
        required=False,
        error_messages=mensajes(
            "El stock mínimo", invalid="El stock mínimo debe ser un número entero."
        ),
    )
    sede_nombre = serializers.CharField(source="sede.nombre", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    categoria_nombre = serializers.CharField(source="producto.categoria.nombre", read_only=True)
    tipo_control_stock = serializers.CharField(source="producto.tipo_control_stock", read_only=True)

    class Meta:
        model = InventarioProducto
        fields = [
            "id",
            "sede",
            "sede_nombre",
            "producto",
            "producto_nombre",
            "categoria_nombre",
            "tipo_control_stock",
            "stock_actual",
            "stock_minimo",
            "disponible",
            "fecha_actualizacion",
        ]
        # the availability switch belongs to HU-13
        read_only_fields = ["id", "disponible", "fecha_actualizacion"]
        # the default unique validator would force `sede` to be required
        validators = []


class InventarioInsumoSerializer(ValidacionInventarioMixin, serializers.ModelSerializer):
    campo_item = "insumo"
    nombre_item = "ingrediente"

    sede = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.filter(activa=True),
        required=False,
        error_messages={
            "does_not_exist": "La sede no existe o está inactiva.",
            "incorrect_type": "La sede debe ser un id numérico.",
        },
    )
    insumo = serializers.PrimaryKeyRelatedField(
        queryset=Insumo.objects.filter(activo=True),
        error_messages={
            "required": "Selecciona el ingrediente.",
            "null": "Selecciona el ingrediente.",
            "does_not_exist": "El ingrediente no existe o está inactivo.",
            "incorrect_type": "El ingrediente debe ser un id numérico.",
        },
    )
    stock_actual = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
        error_messages=mensajes(
            "El stock actual",
            max_digits="El stock actual es demasiado grande.",
            max_decimal_places="El stock actual admite máximo 3 decimales.",
            max_whole_digits="El stock actual es demasiado grande.",
        ),
    )
    stock_minimo = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
        required=False,
        error_messages=mensajes(
            "El stock mínimo",
            max_digits="El stock mínimo es demasiado grande.",
            max_decimal_places="El stock mínimo admite máximo 3 decimales.",
            max_whole_digits="El stock mínimo es demasiado grande.",
        ),
    )
    sede_nombre = serializers.CharField(source="sede.nombre", read_only=True)
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="insumo.unidad_medida", read_only=True)

    class Meta:
        model = InventarioInsumo
        fields = [
            "id",
            "sede",
            "sede_nombre",
            "insumo",
            "insumo_nombre",
            "unidad_medida",
            "stock_actual",
            "stock_minimo",
            "disponible",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "disponible", "fecha_actualizacion"]
        validators = []
