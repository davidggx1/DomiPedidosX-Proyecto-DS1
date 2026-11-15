"""
HU-50 · Correos de estado del pedido al cliente.

- Confirmación: al crearse el pedido, con el desglose de productos, el costo de
  domicilio, el total y el número de orden (criterio 1).
- Cambios de estado: "Aprobado", "En preparación", "En camino" y "Entregado"
  (criterio 2). Los pasos internos (listo para despacho, recogido) no se avisan.
- Cancelación: el correo explica el motivo guardado en el pedido (criterio 3),
  sea que cancele el cliente, la sede o el sistema (pedido vencido).
- Cada correo va por la cola de Celery (usuarios.tasks.encolar_correo, SCRUM-119):
  con el worker llega en segundos, y si el servidor de correo falla se reintenta
  (criterio 4).
- Un fallo aquí (plantilla, base de datos, SMTP) nunca rompe el pedido ni el cambio
  de estado: solo queda en el log (criterio 5).

Se llaman después del commit: `servicios.confirmar_pedido` y los receivers de
`estados.estado_pedido_cambiado` (pedidos/signals.py).
"""
import logging

from django.conf import settings
from django.template.loader import render_to_string

from usuarios.tasks import encolar_correo

from .models import EstadoFactura, EstadoPedido

logger = logging.getLogger(__name__)

# Estado nuevo -> (asunto, titular, mensaje). {sede} y {numero} se rellenan al enviar.
AVISOS_ESTADO = {
    EstadoPedido.RECIBIDO: (
        "Pedido {numero} aprobado",
        "¡Tu pedido fue aprobado!",
        "{sede} aprobó tu pedido y pronto empezará a prepararse.",
    ),
    EstadoPedido.EN_PREPARACION: (
        "Pedido {numero} en preparación",
        "Tu pedido está en preparación",
        "La cocina de {sede} ya está preparando tu pedido.",
    ),
    EstadoPedido.EN_CAMINO: (
        "Pedido {numero} en camino",
        "Tu pedido va en camino",
        "Tu pedido salió de {sede} y va hacia tu dirección.",
    ),
    EstadoPedido.ENTREGADO: (
        "Pedido {numero} entregado",
        "Tu pedido fue entregado",
        "¡Buen provecho! Gracias por pedir en {sede}.",
    ),
    EstadoPedido.CANCELADO: (
        "Pedido {numero} cancelado",
        "Tu pedido fue cancelado",
        "Tu pedido {numero} de {sede} fue cancelado.",
    ),
}


def _pesos(valor):
    """12500 -> "$12.500" (pesos colombianos, sin decimales)."""
    return f"${valor:,.0f}".replace(",", ".")


def _items(pedido):
    items = []
    detalles = pedido.detalles.select_related("producto", "combo", "producto_tamano").prefetch_related(
        "adiciones__adicion"
    )
    for d in detalles:
        nombre = d.producto.nombre if d.producto_id else d.combo.nombre
        if d.producto_tamano_id:
            nombre = f"{nombre} ({d.producto_tamano.nombre})"
        items.append({
            "nombre": nombre,
            "cantidad": d.cantidad,
            "subtotal": _pesos(d.subtotal),
            "adiciones": [f"{a.cantidad} x {a.adicion.nombre}" for a in d.adiciones.all()],
            "observaciones": d.observaciones,
        })
    return items


def _contexto(pedido):
    contexto = {
        "cliente": pedido.cliente.nombres,
        "numero": pedido.numero_pedido,
        "sede": pedido.sede.nombre,
        "direccion": pedido.entrega_direccion,
        "tiempo_estimado": pedido.tiempo_estimado_entrega,
        "enlace": f"{settings.FRONTEND_URL}/mis-pedidos/{pedido.pk}",
        "factura": None,
    }
    factura = getattr(pedido, "factura", None)
    if factura is not None:
        contexto["factura"] = {
            "subtotal": _pesos(factura.subtotal),
            "iva": _pesos(factura.iva),
            "domicilio": _pesos(factura.costo_domicilio),
            "descuento": _pesos(factura.valor_descuento) if factura.valor_descuento else "",
            "total": _pesos(factura.total),
            "metodo_pago": factura.get_metodo_pago_display(),
            "pagada": factura.estado_factura == EstadoFactura.PAGADA,
        }
    return contexto


def _destinatario(pedido):
    """Correo del cliente, o None (pedidos de mostrador sin cliente o cuenta sin correo)."""
    if pedido.cliente is None:
        return None
    return pedido.cliente.usuario.email or None


def _enviar(plantilla, asunto, contexto, destinatario):
    texto = render_to_string(f"pedidos/correo/{plantilla}.txt", contexto)
    html = render_to_string(f"pedidos/correo/{plantilla}.html", contexto)
    encolar_correo(asunto, texto, [destinatario], html=html)


def enviar_correo_confirmacion(pedido):
    """Correo de confirmación con el desglose del pedido. Nunca lanza."""
    try:
        destinatario = _destinatario(pedido)
        if destinatario is None:
            return
        contexto = _contexto(pedido)
        contexto["items"] = _items(pedido)
        _enviar("confirmacion", f"Recibimos tu pedido {pedido.numero_pedido}", contexto, destinatario)
    except Exception:
        logger.exception("No se pudo enviar el correo de confirmación del pedido %s", pedido.pk)


def enviar_correo_estado(pedido):
    """Correo del estado actual del pedido, si es de los que se avisan. Nunca lanza."""
    try:
        aviso = AVISOS_ESTADO.get(pedido.estado)
        destinatario = _destinatario(pedido)
        if aviso is None or destinatario is None:
            return
        asunto, titular, mensaje = aviso
        datos = {"numero": pedido.numero_pedido, "sede": pedido.sede.nombre}
        contexto = _contexto(pedido)
        contexto.update({
            "titular": titular,
            "mensaje": mensaje.format(**datos),
            "cancelado": pedido.estado == EstadoPedido.CANCELADO,
            "motivo": pedido.motivo_cancelacion,
        })
        _enviar("estado", asunto.format(**datos), contexto, destinatario)
    except Exception:
        logger.exception("No se pudo enviar el correo de estado del pedido %s", pedido.pk)
