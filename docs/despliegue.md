# Despliegue en la nube (SCRUM-143)

Guía para publicar DomiPedidosX con servicios gratuitos. Sirve también como
**manual de despliegue** de la documentación final (SCRUM-144).

```
Navegador ──► Vercel (frontend React)
   │
   └──► Render: domipedidosx-api ── Daphne: API REST + WebSockets
                                  └ Celery worker + beat (correos, vencer pedidos)
          │            │
          │            └──► Render Key Value (Redis): canal de WebSockets y cola de Celery
          ├──► Supabase: PostgreSQL (datos) + Storage (fotos de productos)
          └──► Brevo: envío de correos por API
```

| Pieza | Servicio | Por qué |
|---|---|---|
| Frontend | **Vercel** | Sugerido en el enunciado; compila Vite y sirve la app con HTTPS. |
| Backend | **Render** (web service gratis) | Sugerido en el enunciado; soporta WebSockets (Daphne). |
| Base de datos | **Supabase** (PostgreSQL) | Sugerido en el enunciado. |
| Fotos de productos | **Supabase Storage** | El disco de Render se borra en cada despliegue. Supabase Storage es compatible con S3 y ya tenemos la cuenta (el enunciado sugiere Cloudinary, pero así usamos un proveedor menos). |
| Redis | **Render Key Value** (gratis) | WebSockets entre procesos y cola de Celery. |
| Correo | **Brevo** (API HTTP) | Render gratis **bloquea los puertos SMTP**, así que el correo sale por API. |

Archivos del repositorio que usa el despliegue:

- `render.yaml`: Blueprint de Render (crea el backend y Redis).
- `backend/build.sh`: instala dependencias, `collectstatic`, `migrate` y, si se pide, `seed_datos`.
- `backend/start.sh`: arranca Celery (worker + beat) en segundo plano y Daphne.
- `frontend/vercel.json`: hace que las rutas de React (`/admin`, `/cocina`...) funcionen al recargar.
- `backend/config/settings.py`: lee todo de variables de entorno (sección "Producción").

> Nunca subas claves al repositorio: van solo en los paneles de Render y Vercel.

---

## 1. Supabase: base de datos y almacenamiento de fotos

1. En [supabase.com](https://supabase.com) crea un proyecto. Región: **East US (North Virginia)**,
   la misma de Render en `render.yaml`. Guarda la contraseña de la base de datos.
2. **Datos de conexión:** botón **Connect** → pestaña de cadenas de conexión → **Session pooler**.
   Anota:
   - `DB_HOST`: algo como `aws-0-us-east-1.pooler.supabase.com`
   - `DB_USER`: algo como `postgres.abcdefghijkl` (lleva el id del proyecto)
   - `DB_PORT`: `5432` y `DB_NAME`: `postgres`

   Usa el **Session pooler**, no la conexión directa: la directa es solo IPv6 y Render no la
   alcanza (error *Network is unreachable*).
3. **Bucket de fotos:** Storage → **New bucket** → nombre `productos` → márcalo **Public**.
4. **Claves S3:** Project Settings → Storage → **S3 Connection**: actívalo y crea un *access key*.
   Anota:
   - `STORAGE_ENDPOINT_URL`: `https://<id>.storage.supabase.co/storage/v1/s3`
   - `STORAGE_REGION`: la región que muestra la página (p. ej. `us-east-1`)
   - `STORAGE_ACCESS_KEY_ID` y `STORAGE_SECRET_ACCESS_KEY`
   - `STORAGE_PUBLIC_DOMAIN`: `<id>.supabase.co/storage/v1/object/public/productos`
     (sin `https://`; `<id>` es el id del proyecto)

## 2. Brevo: correos

1. Crea una cuenta gratis en [brevo.com](https://www.brevo.com).
2. **Senders, domains & IPs → Senders:** agrega y verifica el correo del equipo
   (p. ej. una cuenta de Gmail creada para el proyecto).
3. **SMTP & API → API keys:** crea una clave. Será `BREVO_API_KEY`.
4. `DEFAULT_FROM_EMAIL` debe usar ese remitente verificado, por ejemplo
   `DomiPedidosX <domipedidosx@gmail.com>`. Si no está verificado, Brevo no envía.

## 3. Render: backend y Redis

1. En [render.com](https://render.com) entra con GitHub → **New → Blueprint**.
2. Elige el repositorio y la rama a desplegar (`develop` mientras se prueba, `main` para la entrega).
   Render lee `render.yaml` y propone crear `domipedidosx-redis` y `domipedidosx-api`.
3. Llena las variables que pide (las demás ya vienen en el Blueprint):

   | Variable | Valor |
   |---|---|
   | `DB_HOST`, `DB_USER`, `DB_PASSWORD` | Paso 1.2 |
   | `STORAGE_*` | Paso 1.4 |
   | `BREVO_API_KEY`, `DEFAULT_FROM_EMAIL` | Paso 2 |
   | `SEED_ADMIN_PASSWORD` | Contraseña del `admin@domipedidosx.local` de producción (no uses la de desarrollo) |
   | `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL` | Por ahora `https://example.com`; se cambian en el paso 5 |

4. **Apply**. El primer build tarda unos minutos: instala, migra la base de Supabase y carga los
   datos de prueba (`CARGAR_DATOS_DEMO=True`).
5. Abre `https://domipedidosx-api.onrender.com/api/docs/` (o la URL que asigne Render):
   debe verse Swagger. El admin de Django queda en `/admin/`.

## 4. Vercel: frontend

1. En [vercel.com](https://vercel.com) entra con GitHub → **Add New → Project** → importa el repositorio.
2. **Root Directory:** `frontend`. Vercel detecta Vite (build `npm run build`, salida `dist`).
3. **Environment Variables:** `VITE_API_URL` = `https://<tu-backend>.onrender.com/api`
   (con `/api` al final y sin `/` final). La app arma la dirección `wss://` de los WebSockets con esta misma URL.
4. **Deploy.** Anota la URL, p. ej. `https://domipedidosx.vercel.app`.

> `VITE_API_URL` se fija al compilar: si cambia, hay que volver a desplegar en Vercel.

## 5. Conectar los dos

En Render → `domipedidosx-api` → **Environment**:

- `CORS_ALLOWED_ORIGINS` = `https://domipedidosx.vercel.app` (varias, separadas por comas, sin `/` final)
- `FRONTEND_URL` = `https://domipedidosx.vercel.app` (enlaces de los correos)

Guarda; Render vuelve a desplegar solo.

## 6. Comprobar que todo funciona

- [ ] La tienda carga el menú y las sedes.
- [ ] Iniciar sesión como `admin@domipedidosx.local` con `SEED_ADMIN_PASSWORD`.
- [ ] Crear zonas de cobertura y franjas de capacidad (el seed no las crea) y hacer un pedido como cliente.
- [ ] El pedido aparece **sin recargar** en Pedidos entrantes (WebSockets por `wss://`).
- [ ] Llega el correo de confirmación (y el de restablecer contraseña).
- [ ] Subir una foto a un producto: se ve en la tienda y su URL es de `supabase.co`.
- [ ] Recargar en una ruta interna (p. ej. `/admin/reportes`) no da 404.
- [ ] Un pedido sin aprobar se cancela solo a los `PEDIDO_PENDIENTE_MINUTOS` (Celery beat).

## 7. Límites del plan gratis

- **Render** duerme el backend tras 15 min sin tráfico; la primera visita tarda cerca de 1 minuto.
  **Antes de una presentación, abre la app unos minutos antes.** Hay 750 horas gratis al mes.
- **Supabase** pausa el proyecto tras 7 días de poca actividad (avisa por correo). No se pierde
  nada: en el panel se pulsa **Resume project**.
- **Render Key Value** guarda todo en memoria y se borra al reiniciar. Aquí no importa: solo
  lleva mensajes de paso (WebSockets y tareas de Celery).
- **Brevo** tiene un límite diario de correos en el plan gratis.
- Render gratis no tiene consola: los comandos de Django se hacen en `build.sh`
  (como `seed_datos`) o desde un computador con el `.env` apuntando a Supabase.

## 8. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| Build falla en `migrate` con *Network is unreachable* | Se usó la conexión directa de Supabase. Usa el **Session pooler** (paso 1.2). |
| `DisallowedHost` / 400 Bad Request | Dominio extra del backend: agrégalo en `DJANGO_ALLOWED_HOSTS`. |
| En el navegador: error de **CORS** | `CORS_ALLOWED_ORIGINS` no tiene la URL exacta de Vercel (con `https://`, sin `/` final). |
| La app llama a `127.0.0.1` | Falta `VITE_API_URL` en Vercel o no se volvió a desplegar después de ponerla. |
| 404 al recargar una página | Falta `frontend/vercel.json` o el Root Directory no es `frontend`. |
| Fotos con error 403 / no se ven | El bucket `productos` no es público o `STORAGE_PUBLIC_DOMAIN` está mal. |
| No llegan correos | Remitente de `DEFAULT_FROM_EMAIL` sin verificar en Brevo, o `BREVO_API_KEY` mal. Revisa los logs de Render. |
| CSRF en `/admin/` con otro dominio | Agrégalo con `https://` en `CSRF_TRUSTED_ORIGINS`. |

Los errores del backend salen en Render → `domipedidosx-api` → **Logs**.

## 9. Actualizar la app desplegada

Render y Vercel vuelven a desplegar solos con cada cambio en la rama conectada (cada PR
integrado). Las migraciones nuevas se aplican en el build.
