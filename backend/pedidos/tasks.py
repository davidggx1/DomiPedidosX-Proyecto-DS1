"""SCRUM-119 · Tareas de Celery de la app pedidos."""
from celery import shared_task

from .vencimiento import vencer_pendientes


@shared_task
def vencer_pedidos_pendientes():
    """Tarea periódica (cada minuto, CELERY_BEAT_SCHEDULE): libera los cupos vencidos."""
    return vencer_pendientes()
