#!/usr/bin/env bash
# SCRUM-143 · Comando de inicio de Render (ver docs/despliegue.md).
#
# El plan gratis de Render no tiene workers aparte, así que el worker de Celery
# (correos) y beat (vencer pedidos pendientes cada minuto) corren en este mismo
# servicio, en segundo plano. Solo si hay Redis: sin REDIS_URL las tareas se
# ejecutan en el momento y no hace falta worker.
set -o errexit

if [ -n "$REDIS_URL" ]; then
  celery -A config worker --beat --pool=solo --concurrency=1 --loglevel=info &
fi

# Daphne atiende HTTP y WebSockets. --proxy-headers: Render pasa el https original.
exec daphne --bind 0.0.0.0 --port "${PORT:-8000}" --proxy-headers config.asgi:application
