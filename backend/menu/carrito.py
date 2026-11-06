"""
HU-21 · Agregar productos personalizados al carrito.

El carrito vive en el cliente (React + localStorage). El backend no lo guarda:
valida cada línea (tamaño, adiciones, exclusiones, cantidad) contra el catálogo
de la sede y calcula su precio. HU-23 reutilizará estas funciones al crear el
pedido.

Vive en un módulo aparte (igual que catalogo.py y disponibilidad.py) para no
chocar con los cambios de gestión del menú en views.py y serializers.py.
"""
from decimal import Decimal

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from inventario.models import InventarioProducto
from sedes.models import Sede

from .catalogo import producto_disponible
from .models import Producto, ProductoAdicion, ProductoInsumo, ProductoTamano


def stock_suficiente(producto, inventario, cantidad):
    """
    Hook de stock. Con control por unidades se compara con el stock de la sede.
    El control por insumos (HU-14) llega en el Sprint 2: por ahora no limita.
    """
    if producto.tipo_control_stock == Producto.TipoControlStock.PRODUCTO:
        return inventario is not None and cantidad <= inventario.stock_actual
    # HU-14 (Sprint 2): revisar InventarioInsumo con la receta del producto.
    return True


def calcular_precio_unitario(producto, tamano, adiciones):
    """
    Precio de una unidad de la línea:
    precio_base + precio adicional del tamaño + Σ(precio adición × cantidad).
    adiciones = [(Adicion, cantidad)].
    """
    precio = producto.precio_base
    if tamano is not None:
        precio += tamano.precio_adicional
    for adicion, cantidad in adiciones:
        precio += adicion.precio * cantidad
    return precio


class AdicionLineaSerializer(serializers.Serializer):
    adicion = serializers.IntegerField(
        error_messages={"required": "Indica la adición.", "invalid": "La adición debe ser un id."}
    )
    cantidad = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": "Indica cuántas unidades de la adición.",
            "invalid": "La cantidad de la adición debe ser un número entero.",
            "min_value": "La cantidad de la adición debe ser al menos 1.",
        },
    )


class LineaCarritoSerializer(serializers.Serializer):
    """Una línea del carrito: producto, tamaño, adiciones, exclusiones y cantidad."""

    producto = serializers.IntegerField(
        error_messages={"required": "Indica el producto.", "invalid": "El producto debe ser un id."}
    )
    tamano = serializers.IntegerField(
        required=False,
        allow_null=True,
        error_messages={"invalid": "El tamaño debe ser un id."},
    )
    adiciones = AdicionLineaSerializer(many=True, required=False, default=list)
    exclusiones = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        error_messages={"not_a_list": "Envía la lista de ingredientes que quieres quitar."},
    )
    cantidad = serializers.IntegerField(
        min_value=1,
        error_messages={
            "required": "Indica la cantidad.",
            "invalid": "La cantidad debe ser un número entero.",
            "min_value": "La cantidad debe ser al menos 1.",
        },
    )

    def validate(self, attrs):
        sede = self.context["sede"]

        producto = Producto.objects.filter(pk=attrs["producto"], activo=True).first()
        if producto is None:
            raise serializers.ValidationError({"producto": "El producto no existe o no está activo."})
        inventario = InventarioProducto.objects.filter(sede=sede, producto=producto).first()
        if not producto_disponible(producto, inventario):
            raise serializers.ValidationError(
                {"producto": f'"{producto.nombre}" no está disponible en esta sede.'}
            )

        tamano = self._validar_tamano(producto, attrs.get("tamano"))
        adiciones = self._validar_adiciones(producto, attrs["adiciones"])
        exclusiones = self._validar_exclusiones(producto, attrs["exclusiones"])
        self._validar_sin_contradicciones(adiciones, exclusiones)

        if not stock_suficiente(producto, inventario, attrs["cantidad"]):
            raise serializers.ValidationError(
                {"cantidad": f"Solo quedan {inventario.stock_actual} unidades de \"{producto.nombre}\"."}
            )

        attrs.update(
            producto=producto,
            tamano=tamano,
            adiciones=adiciones,
            exclusiones=exclusiones,
        )
        return attrs

    def _validar_tamano(self, producto, tamano_id):
        tamanos = ProductoTamano.objects.filter(producto=producto, activo=True)
        if tamano_id is None:
            if tamanos.exists():
                raise serializers.ValidationError({"tamano": "Elige un tamaño."})
            return None
        tamano = tamanos.filter(pk=tamano_id).first()
        if tamano is None:
            raise serializers.ValidationError({"tamano": "El tamaño no existe para este producto."})
        return tamano

    def _validar_adiciones(self, producto, adiciones):
        ids = [item["adicion"] for item in adiciones]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"adiciones": "No repitas una adición: usa su cantidad."})
        vinculos = {
            vinculo.adicion_id: vinculo
            for vinculo in ProductoAdicion.objects.filter(
                producto=producto, adicion_id__in=ids, adicion__activa=True
            ).select_related("adicion")
        }
        resultado = []
        for item in adiciones:
            vinculo = vinculos.get(item["adicion"])
            if vinculo is None:
                raise serializers.ValidationError(
                    {"adiciones": "Una de las adiciones no está disponible para este producto."}
                )
            if item["cantidad"] > vinculo.max_cantidad:
                raise serializers.ValidationError(
                    {
                        "adiciones": (
                            f"Puedes agregar máximo {vinculo.max_cantidad} de "
                            f'"{vinculo.adicion.nombre}".'
                        )
                    }
                )
            resultado.append((vinculo.adicion, item["cantidad"]))
        return resultado

    def _validar_exclusiones(self, producto, ids):
        ingredientes = {
            ingrediente.id: ingrediente
            for ingrediente in ProductoInsumo.objects.filter(
                producto=producto, pk__in=ids
            ).select_related("insumo")
        }
        resultado = []
        for ingrediente_id in dict.fromkeys(ids):
            ingrediente = ingredientes.get(ingrediente_id)
            if ingrediente is None:
                raise serializers.ValidationError(
                    {"exclusiones": "Uno de los ingredientes no pertenece a este producto."}
                )
            if not ingrediente.es_excluible:
                raise serializers.ValidationError(
                    {"exclusiones": f'No puedes quitar "{ingrediente.insumo.nombre}": es obligatorio.'}
                )
            resultado.append(ingrediente)
        return resultado

    def _validar_sin_contradicciones(self, adiciones, exclusiones):
        # No se puede quitar un ingrediente base y a la vez agregar la adición
        # que usa ese mismo insumo (sin queso + queso extra).
        quitados = {ingrediente.insumo_id: ingrediente for ingrediente in exclusiones}
        for adicion, _ in adiciones:
            ingrediente = quitados.get(adicion.insumo_id)
            if ingrediente is not None:
                raise serializers.ValidationError(
                    {
                        "exclusiones": (
                            f'No puedes quitar "{ingrediente.insumo.nombre}" y agregar '
                            f'"{adicion.nombre}" a la vez.'
                        )
                    }
                )


class ValidarLineaCarritoView(APIView):
    """
    POST /api/menu/sedes/<id>/carrito/linea/
         {"producto": 1, "tamano": 2, "adiciones": [{"adicion": 3, "cantidad": 2}],
          "exclusiones": [4], "cantidad": 1}

    Valida una línea antes de agregarla o modificarla en el carrito y devuelve
    su precio. Es público, igual que el menú.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=LineaCarritoSerializer,
        responses=inline_serializer(
            "LineaCarritoPrecio",
            {
                "precio_unitario": serializers.DecimalField(max_digits=10, decimal_places=2),
                "subtotal": serializers.DecimalField(max_digits=12, decimal_places=2),
            },
        ),
    )
    def post(self, request, sede_pk):
        sede = get_object_or_404(Sede, pk=sede_pk, activa=True)
        serializer = LineaCarritoSerializer(data=request.data, context={"sede": sede})
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        precio_unitario = calcular_precio_unitario(datos["producto"], datos["tamano"], datos["adiciones"])
        subtotal = precio_unitario * datos["cantidad"]
        return Response(
            {
                "precio_unitario": f"{precio_unitario.quantize(Decimal('0.01'))}",
                "subtotal": f"{subtotal.quantize(Decimal('0.01'))}",
            }
        )

class ResumenCarritoSerializer(serializers.Serializer):
    """
    HU-22: Recibe la lista de líneas del carrito y calcula el subtotal, domicilio y total.
    """
    lineas = LineaCarritoSerializer(many=True, required=True, allow_empty=True)

    def validate(self, attrs):
        # Valida cada línea reutilizando la lógica de LineaCarritoSerializer
        return attrs


class CalcularResumenCarritoView(APIView):
    """
    POST /api/menu/sedes/<sede_pk>/carrito/resumen/

    Payload de entrada:
    {
        "lineas": [
            {
                "producto": 1,
                "tamano": 2,
                "adiciones": [{"adicion": 3, "cantidad": 1}],
                "exclusiones": [],
                "cantidad": 2
            }
        ]
    }

    Respuesta (HU-22):
    {
        "subtotal": "54000.00",
        "costo_domicilio": "4000.00",
        "total": "58000.00",
        "lineas": [ ... precio unitario y subtotal por línea ... ]
    }
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=ResumenCarritoSerializer,
        responses=inline_serializer(
            "ResumenCarritoSalida",
            {
                "subtotal": serializers.DecimalField(max_digits=12, decimal_places=2),
                "costo_domicilio": serializers.DecimalField(max_digits=10, decimal_places=2),
                "total": serializers.DecimalField(max_digits=12, decimal_places=2),
                "lineas": serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def post(self, request, sede_pk):
        sede = get_object_or_404(Sede, pk=sede_pk, activa=True)
        serializer = ResumenCarritoSerializer(data=request.data, context={"sede": sede})
        serializer.is_valid(raise_exception=True)

        lineas_validadas = serializer.validated_data["lineas"]
        subtotal_acumulado = Decimal("0.00")
        lineas_desglosadas = []

        for item in lineas_validadas:
            precio_unitario = calcular_precio_unitario(
                item["producto"], item["tamano"], item["adiciones"]
            )
            subtotal_linea = precio_unitario * item["cantidad"]
            subtotal_acumulado += subtotal_linea

            lineas_desglosadas.append(
                {
                    "producto_id": item["producto"].id,
                    "producto_nombre": item["producto"].nombre,
                    "cantidad": item["cantidad"],
                    "precio_unitario": f"{precio_unitario.quantize(Decimal('0.01'))}",
                    "subtotal_linea": f"{subtotal_linea.quantize(Decimal('0.01'))}",
                }
            )

        # HU-22: Tarifa fija de domicilio provisional por sede para el PMV (Sprint 2)
        costo_domicilio = getattr(sede, "tarifa_domicilio_fija", Decimal("4000.00"))
        if subtotal_acumulado == Decimal("0.00"):
            costo_domicilio = Decimal("0.00")

        total = subtotal_acumulado + costo_domicilio

        return Response(
            {
                "subtotal": f"{subtotal_acumulado.quantize(Decimal('0.01'))}",
                "costo_domicilio": f"{costo_domicilio.quantize(Decimal('0.01'))}",
                "total": f"{total.quantize(Decimal('0.01'))}",
                "lineas": lineas_desglosadas,
            },
            status=status.HTTP_200_OK,
        )