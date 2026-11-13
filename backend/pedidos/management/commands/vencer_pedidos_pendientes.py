"""Ejecuta a mano el vencimiento de pedidos pendientes (útil sin Celery beat)."""
from django.conf import settings
from django.core.management.base import BaseCommand

from pedidos.vencimiento import vencer_pendientes


class Command(BaseCommand):
    help = "Cancela los pedidos que llevan más de PEDIDO_PENDIENTE_MINUTOS sin aprobar y libera su cupo y su stock."

    def handle(self, *args, **options):
        cancelados = vencer_pendientes()
        self.stdout.write(self.style.SUCCESS(
            f"{cancelados} pedido(s) cancelado(s) por pasar más de "
            f"{settings.PEDIDO_PENDIENTE_MINUTOS} minutos sin aprobar."
        ))
