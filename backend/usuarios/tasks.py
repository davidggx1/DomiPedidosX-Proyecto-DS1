"""
SCRUM-119 · Envío de correos en segundo plano (base de HU-05, HU-25 y HU-50).

Quien necesita mandar un correo llama a `encolar_correo(...)`:
- Con Redis, el correo va a la cola y lo envía el worker; si el servidor de
  correo falla, el worker reintenta hasta 3 veces, con un minuto de espera.
- Sin Redis, se envía en el momento.
- Si Redis no responde al encolar, se envía en el momento en lugar de perderlo.

Un correo que no se pudo enviar nunca rompe la acción que lo pidió (un pedido,
una cancelación...): solo queda registrado en el log.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_correo(self, asunto, mensaje, destinatarios):
    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(destinatarios),
        )
    except Exception as error:
        if self.request.is_eager or self.request.retries >= self.max_retries:
            logger.exception("No se pudo enviar el correo %r a %s", asunto, destinatarios)
            return
        logger.warning("Falló el envío del correo %r; se reintentará: %s", asunto, error)
        raise self.retry(exc=error)


def encolar_correo(asunto, mensaje, destinatarios):
    """Manda el correo a la cola (o lo envía en el momento si no hay Redis)."""
    try:
        enviar_correo.delay(asunto, mensaje, list(destinatarios))
    except Exception:
        logger.exception("No se pudo encolar el correo %r; se envía en el momento", asunto)
        enviar_correo.apply(args=(asunto, mensaje, list(destinatarios)))
