"""Confirmación de pedido (HU-23): toda la lógica en una sola transacción."""
import math
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .stock import descontar_stock

from inventario.models import InventarioInsumo, InventarioProducto
from menu.models import (
    Adicion,
    Producto,
    ProductoAdicion,
    ProductoInsumo,
    ProductoTamano,
)
from promociones.models import Combo, ComboProducto, ComboSede
from sedes.models import Sede, ZonaCobertura, CapacidadSede
from usuarios.models import DireccionEntrega
from .eventos import notificar_pedido
from .models import (
    ConsumoCupoCombo,
    DetallePedido,
    DetallePedidoAdicion,
    DetallePedidoExclusion,
    EstadoFactura,
    EstadoPedido,
    Factura,
    HistorialEstadoPedido,
    MetodoPago,
    Notificacion,
    OrigenPedido,
    Pedido,
    TipoNotificacion,
)

DIAS_MAP = {
    0: 'lunes',
    1: 'martes',
    2: 'miercoles',
    3: 'jueves',
    4: 'viernes',
    5: 'sabado',
    6: 'domingo',
}

# --- Configuración (confirmar con el equipo) --------------------------------
IVA = Decimal("0.19")
# True: los precios del menú ya incluyen IVA (el IVA se informa, no se suma).
PRECIOS_INCLUYEN_IVA = True
# ----------------------------------------------------------------------------

CENTAVOS = Decimal("0.01")
CERO = Decimal("0")


class ErrorConfirmacion(APIException):
    """400 con un detalle y, opcionalmente, los ítems con problemas."""

    status_code = 400
    default_code = "confirmacion_invalida"

    def __init__(self, mensaje, items=None):
        self.detail = {"detail": mensaje, "items": items or []}


def _redondear(valor):
    return valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _distancia_km(lat1, lon1, lat2, lon2):
    """Fórmula de Haversine."""
    radio_tierra = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radio_tierra * math.asin(math.sqrt(a))


def _zona_de_cobertura(sede, direccion):
    """Zona activa de la sede que contiene la dirección (la de menor radio si hay varias)."""
    candidatas = [
        z
        for z in ZonaCobertura.objects.filter(sede=sede, activo=True)
        if _distancia_km(
            direccion.latitud, direccion.longitud, z.centro_latitud, z.centro_longitud
        )
        <= z.radio
    ]
    return min(candidatas, key=lambda z: z.radio) if candidatas else None


def _siguiente_folio():
    # Secuencial por día. Si dos pedidos calculan el mismo, la restricción unique
    # de la base lo rechaza y confirmar_pedido reintenta.
    prefijo = f"P-{timezone.localdate():%Y%m%d}-"
    ultimo = (
        Pedido.objects.filter(numero_pedido__startswith=prefijo)
        .order_by("-numero_pedido")
        .values_list("numero_pedido", flat=True)
        .first()
    )
    secuencia = int(ultimo[len(prefijo):]) + 1 if ultimo else 1
    return f"{prefijo}{secuencia:04d}"


def _err(errores, indice, nombre, motivo):
    errores.append({"indice": indice, "nombre": nombre, "motivo": motivo})


def _preparar_carrito(items, sede):
    """Valida catálogo y disponibilidad, y calcula precios desde la base de datos.

    Devuelve (lineas, consumos_cupo, errores). Debe ejecutarse dentro de una
    transacción: bloquea las filas de ComboSede para proteger el cupo diario.
    """
    hoy = timezone.localdate()
    errores = []

    producto_ids = {i["producto_id"] for i in items if i.get("producto_id")}
    combo_ids = {i["combo_id"] for i in items if i.get("combo_id")}

    combos = {c.pk: c for c in Combo.objects.filter(pk__in=combo_ids)}
    incluidos = defaultdict(list)
    for cp in ComboProducto.objects.select_related("producto__categoria").filter(
        combo_id__in=list(combos)
    ):
        incluidos[cp.combo_id].append(cp)
        producto_ids.add(cp.producto_id)

    productos = {
        p.pk: p
        for p in Producto.objects.select_related("categoria").filter(pk__in=producto_ids)
    }
    tamanos = {t.pk: t for t in ProductoTamano.objects.filter(producto_id__in=producto_ids)}
    con_tamanos = {t.producto_id for t in tamanos.values() if t.activo}

    adicion_ids = {a["adicion_id"] for i in items for a in i.get("adiciones", [])}
    adiciones = {
        a.pk: a for a in Adicion.objects.select_related("insumo").filter(pk__in=adicion_ids)
    }
    permitidas = {
        (pa.producto_id, pa.adicion_id): pa.max_cantidad
        for pa in ProductoAdicion.objects.filter(
            producto_id__in=producto_ids, adicion_id__in=adicion_ids
        )
    }

    recetas = defaultdict(dict)
    nombres_insumo = {}
    for pi in ProductoInsumo.objects.select_related("insumo").filter(
        producto_id__in=producto_ids
    ):
        recetas[pi.producto_id][pi.insumo_id] = pi
        nombres_insumo[pi.insumo_id] = pi.insumo.nombre

    # Bloqueo de filas: dos checkouts no pueden pasarse del cupo diario del combo.
    combos_sede = {
        cs.combo_id: cs
        for cs in ComboSede.objects.select_for_update()
        .filter(combo_id__in=list(combos), sede=sede, activo=True)
        .order_by("pk")
    }
    cs_por_pk = {cs.pk: cs for cs in combos_sede.values()}

    # Lo que pide el carrito, acumulado, y qué ítems lo piden (para los mensajes).
    cant_producto, cant_cupo = defaultdict(int), defaultdict(int)
    cant_insumo = defaultdict(lambda: CERO)
    insumos_adicion = {}
    quien = defaultdict(set)
    nombres_item = {}

    def pedir_producto(idx, producto, cantidad, excluidos=frozenset()):
        control = producto.tipo_control_stock
        if control == Producto.TipoControlStock.PRODUCTO:
            cant_producto[producto.pk] += cantidad
            quien[("p", producto.pk)].add(idx)
        elif control == Producto.TipoControlStock.INSUMOS:
            for insumo_id, pi in recetas[producto.pk].items():
                if insumo_id in excluidos:
                    continue
                cant_insumo[insumo_id] += pi.cantidad_necesaria * cantidad
                quien[("i", insumo_id)].add(idx)

    lineas = []
    for idx, item in enumerate(items):
        cantidad = item["cantidad"]

        if item.get("producto_id"):
            producto = productos.get(item["producto_id"])
            if producto is None or not producto.activo or not producto.categoria.activa:
                _err(errores, idx, producto.nombre if producto else "",
                     "Producto no disponible en el menú.")
                continue
            nombres_item[idx] = producto.nombre
            antes = len(errores)

            tamano = None
            if item.get("tamano_id"):
                tamano = tamanos.get(item["tamano_id"])
                if tamano is None or tamano.producto_id != producto.pk or not tamano.activo:
                    _err(errores, idx, producto.nombre, "Tamaño no disponible.")
            elif producto.pk in con_tamanos:
                _err(errores, idx, producto.nombre, "Debes elegir un tamaño.")

            extras = []
            for a in item.get("adiciones", []):
                adicion = adiciones.get(a["adicion_id"])
                maximo = permitidas.get((producto.pk, a["adicion_id"]))
                if (
                    adicion is None
                    or maximo is None
                    or not adicion.activa
                    or not adicion.insumo.activo
                ):
                    _err(errores, idx, producto.nombre,
                         "Una adición no está disponible para este producto.")
                elif a["cantidad"] > maximo:
                    _err(errores, idx, producto.nombre,
                         f"Máximo {maximo} de «{adicion.nombre}» por unidad.")
                else:
                    extras.append((adicion, a["cantidad"]))

            excluidos = []
            for insumo_id in item.get("exclusiones", []):
                pi = recetas[producto.pk].get(insumo_id)
                if pi is None or not pi.es_excluible:
                    _err(errores, idx, producto.nombre,
                         "Un ingrediente no se puede excluir de este producto.")
                else:
                    excluidos.append(pi.insumo)

            if len(errores) > antes:
                continue

            for adicion, _ in extras:
                insumos_adicion[adicion.insumo_id] = adicion.insumo.nombre
                quien[("a", adicion.insumo_id)].add(idx)
            pedir_producto(idx, producto, cantidad, {i.pk for i in excluidos})

            precio_unitario = producto.precio_base + (
                tamano.precio_adicional if tamano else CERO
            )
            extra_unitario = sum((a.precio * c for a, c in extras), CERO)
            lineas.append({
                "producto": producto, "combo": None, "tamano": tamano,
                "cantidad": cantidad, "precio_unitario": precio_unitario,
                "subtotal": (precio_unitario + extra_unitario) * cantidad,
                "adiciones": extras, "exclusiones": excluidos,
                "observaciones": item.get("observaciones", ""),
            })

        else:
            combo = combos.get(item["combo_id"])
            nombres_item[idx] = combo.nombre if combo else ""
            cs = combos_sede.get(item["combo_id"])
            if (
                combo is None
                or not combo.activo
                or not (combo.fecha_inicio <= hoy <= combo.fecha_vencimiento)
            ):
                _err(errores, idx, nombres_item[idx], "Combo no disponible.")
                continue
            if cs is None:
                _err(errores, idx, combo.nombre, "Combo no disponible en esta sede.")
                continue
            antes = len(errores)
            for cp in incluidos[combo.pk]:
                if not cp.producto.activo or not cp.producto.categoria.activa:
                    _err(errores, idx, combo.nombre,
                         f"«{cp.producto.nombre}» no está disponible.")
            if len(errores) > antes:
                continue
            for cp in incluidos[combo.pk]:
                pedir_producto(idx, productos[cp.producto_id], cantidad * cp.cantidad)
            cant_cupo[cs.pk] += cantidad
            quien[("c", cs.pk)].add(idx)
            lineas.append({
                "producto": None, "combo": combo, "tamano": None,
                "cantidad": cantidad, "precio_unitario": combo.precio,
                "subtotal": combo.precio * cantidad,
                "adiciones": [], "exclusiones": [],
                "observaciones": item.get("observaciones", ""),
            })

    def error_para(clave, motivo):
        for idx in sorted(quien[clave]):
            _err(errores, idx, nombres_item.get(idx, ""), motivo)

    # Existencias de productos terminados.
    inv_producto = {
        i.producto_id: i
        for i in InventarioProducto.objects.select_for_update()
        .filter(sede=sede, producto_id__in=list(cant_producto))
        .order_by("pk")
    }
    for pid, pedido_cant in cant_producto.items():
        inv = inv_producto.get(pid)
        if inv is None or not inv.disponible or inv.stock_actual <= 0:
            error_para(("p", pid), "Producto agotado.")
        elif inv.stock_actual < pedido_cant:
            error_para(("p", pid), f"Solo quedan {inv.stock_actual} unidades.")

    # Existencias de insumos (recetas) y de los insumos de las adiciones.
    inv_insumo = {
        i.insumo_id: i
        for i in InventarioInsumo.objects.select_for_update()
        .filter(sede=sede, insumo_id__in=list(set(cant_insumo) | set(insumos_adicion)))
        .order_by("pk")
    }
    for iid, pedido_cant in cant_insumo.items():
        inv = inv_insumo.get(iid)
        if inv is None or not inv.disponible or inv.stock_actual < pedido_cant:
            error_para(("i", iid), "No hay existencias suficientes para preparar este producto.")
    for iid in insumos_adicion:
        inv = inv_insumo.get(iid)
        if inv is None or not inv.disponible or inv.stock_actual <= 0:
            error_para(("a", iid), "Una adición está agotada.")

    # Cupo diario de combos (no cuenta pedidos cancelados: el cupo se devuelve).
    consumos = []
    for cs_pk, pedido_cant in cant_cupo.items():
        cs = cs_por_pk[cs_pk]
        if cs.cupo_max_diario is not None:
            usado = (
                ConsumoCupoCombo.objects.filter(combo_sede=cs, fecha_consumo__date=hoy)
                .exclude(pedido__estado=EstadoPedido.CANCELADO)
                .aggregate(t=Sum("cantidad_usada"))["t"]
                or 0
            )
            restante = max(cs.cupo_max_diario - usado, 0)
            if pedido_cant > restante:
                error_para(("c", cs_pk), f"Cupo diario del combo agotado (quedan {restante}).")
        consumos.append((cs, pedido_cant))

    stock = {
        "inv_producto": inv_producto,
        "inv_insumo": inv_insumo,
        "cant_producto": dict(cant_producto),
        "cant_insumo": dict(cant_insumo),
    }
    return lineas, consumos, errores, stock


def _crear_notificacion(usuario, pedido):
    Notificacion.objects.create(
        usuario=usuario,
        pedido=pedido,
        mensaje=f"Tu pedido {pedido.numero_pedido} fue recibido y está pendiente de aprobación.",
        tipo=TipoNotificacion.PEDIDO_CONFIRMADO,
    )


@transaction.atomic
def confirmar_pedido(*, usuario, cliente, datos):
    """Crea el pedido en 'Pendiente de aprobación'. Devuelve (pedido, factura)."""
    sede = Sede.objects.filter(pk=datos["sede_id"], activa=True).first()
    if sede is None:
        raise ValidationError({"sede_id": ["La sede no existe o no está activa."]})

    direccion = DireccionEntrega.objects.filter(
        pk=datos["direccion_id"], cliente=cliente, activa=True
    ).first()
    if direccion is None:
        raise ValidationError({"direccion_id": ["La dirección no existe o no es tuya."]})

    zona = _zona_de_cobertura(sede, direccion)
    if zona is None:
        raise ValidationError(
            {"direccion_id": ["La dirección está fuera de la cobertura de esta sede."]}
        )

    lineas, consumos, errores, stock = _preparar_carrito(datos["items"], sede)
    if errores:
        raise ErrorConfirmacion("Algunos ítems no se pueden confirmar.", errores)

    subtotal = sum((l["subtotal"] for l in lineas), CERO)
    if subtotal < zona.pedido_minimo:
        raise ErrorConfirmacion(
            f"El pedido mínimo para tu zona es ${zona.pedido_minimo:,.0f}."
        )

    costo_domicilio = zona.tarifa_domicilio
    if PRECIOS_INCLUYEN_IVA:
        iva = _redondear(subtotal - subtotal / (1 + IVA))
        total = subtotal + costo_domicilio
    else:
        iva = _redondear(subtotal * IVA)
        total = subtotal + iva + costo_domicilio

    # Folio único: si dos pedidos calculan el mismo, la base rechaza el segundo.
    for _ in range(5):
        try:
            with transaction.atomic():  # savepoint
                pedido = Pedido(
                    numero_pedido=_siguiente_folio(),
                    sede=sede,
                    cliente=cliente,
                    zona_cobertura=zona,
                    origen=OrigenPedido.WEB,
                    estado=EstadoPedido.PENDIENTE_APROBACION,
                    tiempo_estimado_entrega=zona.tiempo_estimado,
                    descripcion=datos.get("observaciones", ""),
                )
                pedido.asignar_direccion_entrega(direccion)
                pedido.save()
            break
        except IntegrityError:
            continue
    else:
        raise ErrorConfirmacion("No se pudo generar el folio del pedido. Intenta de nuevo.")

    for l in lineas:
        detalle = DetallePedido.objects.create(
            pedido=pedido,
            producto=l["producto"],
            combo=l["combo"],
            producto_tamano=l["tamano"],
            cantidad=l["cantidad"],
            precio_unitario=l["precio_unitario"],
            subtotal=l["subtotal"],
            observaciones=l["observaciones"],
        )
        DetallePedidoAdicion.objects.bulk_create([
            DetallePedidoAdicion(
                detalle_pedido=detalle, adicion=a, cantidad=c, precio_unitario=a.precio
            )
            for a, c in l["adiciones"]
        ])
        DetallePedidoExclusion.objects.bulk_create([
            DetallePedidoExclusion(
                detalle_pedido=detalle, insumo=i, nombre_insumo=i.nombre
            )
            for i in l["exclusiones"]
        ])

    # Pago simulado: tarjeta y transferencia quedan pagadas; efectivo, pendiente.
    metodo = datos["metodo_pago"]
    factura = Factura.objects.create(
        pedido=pedido,
        numero=f"F-{pedido.numero_pedido[2:]}",
        subtotal=subtotal,
        iva=iva,
        costo_domicilio=costo_domicilio,
        valor_descuento=CERO,
        total=total,
        metodo_pago=metodo,
        estado_factura=(
            EstadoFactura.PENDIENTE if metodo == MetodoPago.EFECTIVO else EstadoFactura.PAGADA
        ),
    )

    for cs, cantidad in consumos:
        ConsumoCupoCombo.objects.create(combo_sede=cs, pedido=pedido, cantidad_usada=cantidad)

    descontar_stock(**stock)

    HistorialEstadoPedido.objects.create(
        pedido=pedido,
        usuario=usuario,
        estado=EstadoPedido.PENDIENTE_APROBACION,
        observacion="Pedido confirmado por el cliente.",
    )
    _crear_notificacion(usuario, pedido)

    # Se envía al confirmarse la transacción (on_commit): el operador solo lo ve
    # si el pedido quedó guardado completo.
    notificar_pedido(pedido)
    return pedido, factura


def obtener_capacidad_franja_actual(sede, fecha_hora=None):
    """
    Retorna el objeto CapacidadSede correspondiente al momento de la compra.
    """
    if fecha_hora is None:
        fecha_hora = timezone.localtime()

    dia_nombre = DIAS_MAP[fecha_hora.weekday()]
    hora_actual = fecha_hora.time()

    # Buscar la franja que coincida con el día y hora actual
    capacidades = CapacidadSede.objects.filter(
        sede=sede,
        hora_inicio__lte=hora_actual,
        hora_fin__gte=hora_actual,
    )

    for cap in capacidades:
        dias_cap = [d.strip().lower() for d in cap.dias_semana.split(',') if d.strip()]
        if dia_nombre in dias_cap:
            return cap

    return None


def validar_disponibilidad_cupo_sede(sede):
    """
    HU-59 Criterio #3: Suma órdenes en 'recibido' y 'en_preparacion'.
    Si supera la capacidad configurada en la franja, bloquea el pedido.
    """
    capacidad = obtener_capacidad_franja_actual(sede)

    # Si no hay capacidad configurada o límite explicito, se permite la operación
    if not capacidad:
        return True, None

    # Métrica: pedidos activos en cocina para esta sede
    pedidos_activos = Pedido.objects.filter(
        sede=sede,
        estado__in=[EstadoPedido.RECIBIDO, EstadoPedido.EN_PREPARACION]
    ).count()

    if pedidos_activos >= capacidad.max_pedidos_simultaneos:
        raise ValidationError({
            "detail": (
                f"La sede '{sede.nombre}' ha alcanzado el límite de pedidos simultáneos en cocina "
                f"({pedidos_activos}/{capacidad.max_pedidos_simultaneos}) para esta franja horaria. "
                "Por favor intente nuevamente en unos minutos."
            ),
            "codigo": "capacidad_maxima_alcanzada"
        })

    return True, capacidad