# Tareas asíncronas (Celery + Redis)

El backend usa **Celery** para el trabajo que no debe hacer esperar al usuario, y **Redis** como cola entre Django y Celery.

| Tarea | Qué hace | Cuándo |
|---|---|---|
| `usuarios.tasks.enviar_correo` | Envía un correo. Si el servidor de correo falla, reintenta 3 veces (cada minuto). | Restablecer contraseña (HU-05), cancelación (HU-25), base de los correos de estado (HU-50) |
| `pedidos.tasks.vencer_pedidos_pendientes` | Cancela los pedidos que llevan más de `PEDIDO_PENDIENTE_MINUTOS` sin que la sede los apruebe. Devuelve su stock y libera su cupo de capacidad. Avisa al cliente. | Cada minuto (Celery beat) |

Un correo que falla **nunca** rompe la acción que lo pidió: solo queda en el log.

## Sin Redis (lo normal en desarrollo)

**No hay que instalar nada.** Si `REDIS_URL` está vacío en `backend/.env`, las tareas se ejecutan en el momento, dentro del mismo proceso de Django: los correos salen en la consola de `runserver`, como antes.

Lo único que no corre solo es la tarea periódica. Para vencer los pedidos pendientes a mano:

```bash
python backend/manage.py vencer_pedidos_pendientes
```

## Con Redis (producción o para probar la cola)

1. **Levanta Redis.** En Windows, lo más simple es Docker Desktop:

   ```bash
   docker run -d --name domipedidos-redis -p 6379:6379 redis:7
   ```

   Redis no tiene versión oficial para Windows: también sirve Memurai (compatible) o Redis dentro de WSL.

2. **Configura `backend/.env`:**

   ```
   REDIS_URL=redis://localhost:6379/0
   ```

   Con eso se activan a la vez la cola de Celery y el tiempo real con Redis (WebSockets entre varios procesos).

3. **Arranca, además de `runserver`, dos terminales más** (con el entorno virtual activo, desde `backend/`):

   ```bash
   # Ejecuta las tareas. En Windows es obligatorio "-P solo".
   celery -A config worker -l info -P solo

   # Dispara las tareas periódicas (vencer pedidos cada minuto).
   celery -A config beat -l info
   ```

   En Linux o macOS se puede omitir `-P solo`.

Si Redis se cae mientras Django corre, los correos no se pierden: se envían en el momento y queda un aviso en el log.

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `REDIS_URL` | vacío | Redis para la cola de Celery y para el tiempo real. Vacío: todo en memoria y tareas al momento. |
| `CELERY_BROKER_URL` | `REDIS_URL` | Solo si la cola debe usar un Redis distinto al del tiempo real. |
| `PEDIDO_PENDIENTE_MINUTOS` | `20` | Minutos que un pedido espera la aprobación antes de cancelarse solo. `0` lo desactiva. |

## Agregar una tarea nueva

1. Créala en `<app>/tasks.py` con `@shared_task`. Celery la encuentra solo.
2. Llámala con `.delay(...)` (con Redis va a la cola; sin Redis corre al momento).
3. Para correos, usa `encolar_correo(asunto, mensaje, [destinatarios])` de `usuarios/tasks.py`.
4. Si es periódica, agrégala a `CELERY_BEAT_SCHEDULE` en `config/settings.py`.

Las pruebas corren siempre sin Redis, con las tareas al momento: `mail.outbox` recibe los correos como antes.
