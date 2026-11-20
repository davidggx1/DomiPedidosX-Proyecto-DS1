#!/usr/bin/env bash
# SCRUM-143 · Comando de build de Render (ver docs/despliegue.md).
# Instala dependencias, junta los estáticos del admin y aplica las migraciones.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Datos de prueba (sedes, menú, usuarios de demo). Render gratis no tiene consola,
# así que se cargan aquí si CARGAR_DATOS_DEMO=True. seed_datos no duplica nada.
if [ "$CARGAR_DATOS_DEMO" = "True" ]; then
  python manage.py seed_datos
fi
