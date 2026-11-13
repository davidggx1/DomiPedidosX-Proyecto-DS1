"""
SCRUM-119 · Motor de tareas asíncronas (Celery + Redis).

- Con Redis configurado (REDIS_URL o CELERY_BROKER_URL), las tareas van a la cola
  y las ejecuta un worker aparte: `celery -A config worker -l info -P solo`.
- Sin Redis (desarrollo local y pruebas), las tareas se ejecutan en el momento,
  dentro del mismo proceso de Django. Así nadie necesita instalar Redis para trabajar.
- Las tareas periódicas (CELERY_BEAT_SCHEDULE) las dispara `celery -A config beat -l info`.

Guía completa: docs/tareas-asincronas.md
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("domipedidosx")
# Toma de settings.py todas las variables que empiezan por CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")
# Registra las tareas de cada app (<app>/tasks.py)
app.autodiscover_tasks()
