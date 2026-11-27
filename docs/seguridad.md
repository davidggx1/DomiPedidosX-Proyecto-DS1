# Seguridad del backend

Prácticas de la Clase 10 de DS1 (recomendaciones de seguridad en Django) aplicadas a las partes
delicadas del sistema. Ya existían antes de este trabajo:

- los secretos van en variables de entorno;
- las cookies son `Secure` en producción;
- los roles se controlan con `rol_requerido`;
- las imágenes subidas se validan;
- las consultas van por el ORM.

El pago simulado no recibe datos de tarjeta, solo `metodo_pago`.

## 1. Fuerza bruta en el login (diapositivas 19 y 43)

Hay dos barreras que se complementan. El código está en `backend/usuarios/intentos_login.py`.

### Límite por IP

`ScopedRateThrottle` de DRF con `throttle_scope = "login"` se aplica a cuatro vistas:

| Endpoint | Vista |
|---|---|
| `POST /api/usuarios/login/` | `LoginView` |
| `POST /api/usuarios/login-personal/` | `LoginPersonalView` |
| `POST /api/auth/token/` (Swagger y Postman) | `LoginView` |
| `POST /api/usuarios/contrasena/solicitar/` y `.../restablecer/` | `SolicitarRestablecimientoView`, `RestablecerContrasenaView` |

- Las cuatro comparten el mismo contador por IP: `LOGIN_RATE_LIMIT`, por defecto `5/min`.
- Pasado el límite, la respuesta es **429**: *"Demasiados intentos. Espera unos minutos e inténtalo de nuevo. Podrás intentarlo en N segundos."*
- La respuesta incluye la cabecera `Retry-After`.

`/api/auth/token/` era el `TokenObtainPairView` de SimpleJWT sin cambios. Sin límite habría sido
una puerta trasera para la fuerza bruta, así que ahora usa `LoginView`. La respuesta es la misma.

### Bloqueo por cuenta

Cada contraseña mala suma un fallo al contador del correo, sin distinguir mayúsculas.

- Al llegar a `LOGIN_FAILS_LIMIT` (5) fallos, ese correo queda bloqueado `LOGIN_FAILS_TIMEOUT` segundos (300), aunque el atacante cambie de IP.
- Mientras dura el bloqueo no se revisa la contraseña: la respuesta es 429.
- Un login exitoso borra el contador.

Los contadores viven en el caché de Django (`CACHES`):

- **Redis** cuando existe `REDIS_URL`, como en Render. Así todos los procesos comparten los contadores.
- **`LocMemCache`** en desarrollo y en las pruebas.

### Registro de intentos fallidos

Cada fallo, cada bloqueo y cada intento sobre una cuenta bloqueada quedan en el log con nivel
`WARNING` (logger `usuarios.intentos_login`), con el correo y la IP. **Nunca se registra la
contraseña.** En producción se ven en los logs de Render:

```
Intento de login fallido 2/5 (correo=ana@correo.com, ip=190.0.0.1)
Cuenta bloqueada 300 s tras 5 intentos fallidos (correo=ana@correo.com, ip=190.0.0.1)
Login rechazado: cuenta bloqueada por intentos fallidos (correo=ana@correo.com, ip=190.0.0.1)
```

### Cambio en el login del frontend

El formulario de login es uno solo. Primero prueba `login-personal` y, si la cuenta no es de
personal, prueba `login`.

- **Antes:** con una contraseña mala hacía las dos peticiones. Cada error de un cliente contaba doble y, tras dos errores, el intento correcto ya recibía 429.
- **Ahora:** `login-personal` responde `"code": "no_es_personal"` solo cuando la contraseña es correcta pero la cuenta no es de personal. Únicamente en ese caso `frontend/src/api/auth.js` prueba el login de cliente.
- Ese código no revela qué correos existen: solo lo recibe quien ya escribió la contraseña correcta.
- Con el 429, la pantalla de login muestra el mensaje del backend.

### Limitaciones conocidas

- **La IP se puede falsificar.** DRF toma la IP de `X-Forwarded-For`, y un atacante puede inventar esa cabecera para saltarse el límite por IP. El bloqueo por cuenta no depende de la IP y sigue funcionando. Para cerrarlo hay que configurar `NUM_PROXIES` en `REST_FRAMEWORK` según los proxies que ponga Render delante.
- **Varias personas pueden compartir una IP.** En una misma red (por ejemplo, la de la universidad) comparten los 5 intentos por minuto. Si estorba, se sube `LOGIN_RATE_LIMIT` en Render.
- **Bloqueo intencional de una cuenta.** Cualquiera puede bloquear una cuenta 5 minutos con 5 contraseñas malas. Es el costo aceptado del bloqueo por cuenta, y por eso dura poco.

## 2. Decoradores de Django en vistas delicadas (diapositiva 38)

Se aplican a las vistas de clase con `method_decorator(..., name="dispatch")`.

### `sensitive_post_parameters("password")`

Si la petición termina en un error 500, el reporte de Django (página de depuración o correo a los
administradores) muestra `********` en lugar de la contraseña. Se aplica en:

- login: `LoginView` y `LoginPersonalView`;
- registro: `RegistroClienteView` y el registro de empleados `EmpleadoManagementView`;
- restablecimiento de contraseña: `RestablecerContrasenaView`.

### `never_cache`

Agrega `Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private`. Así, ni el
navegador ni un proxy guardan copias de respuestas con datos personales o de dinero (por ejemplo,
en un computador compartido).

| Datos | Vistas |
|---|---|
| Crear pedido / checkout | `ConfirmarPedidoView`, `CrearPedidoOperadorView` |
| Perfil | `PerfilClienteView`, `PerfilPersonalView` |
| Mis pedidos y carrito | `MisPedidosView`, `CarritoGuardadoView` |
| Reportes del admin | `ReporteVentasView`, `ReporteTiemposView`, `ReporteDemandaView`, `ResumenDiaView`, `IndicadoresDiaView` |
| Personal (lista y contraseña inicial) | `EmpleadoManagementView` |

El menú público y las demás vistas no lo llevan.

## 3. Configuración de producción (checklists, diapositivas 44-47)

En `backend/config/settings.py`, dentro de `if not DEBUG:`:

| Setting | Valor | Para qué |
|---|---|---|
| `SECURE_HSTS_SECONDS` | 1 año (variable `SECURE_HSTS_SECONDS`) | El navegador solo usa https con el dominio |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | Lo mismo para los subdominios |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | El navegador no "adivina" el tipo de un archivo |
| `X_FRAME_OPTIONS` | `"DENY"` | Nadie puede meter el sitio en un `<iframe>` (clickjacking) |
| `SECURE_REFERRER_POLICY` | `"same-origin"` | Las URL internas no se envían a otros sitios |
| `SECURE_SSL_REDIRECT` | `True` | http se redirige a https |
| `SECURE_REDIRECT_EXEMPT` | `[r"^api/docs/$"]` | Excepción para el health check |

El health check de Render (`healthCheckPath: /api/docs/` en `render.yaml`) llega por http
interno. Si se redirigiera, Render creería que el servicio está caído.

**Antes de desplegar:** si en Render existe la variable `SECURE_HSTS_SECONDS=0`, hay que borrarla
o cambiarla; si no, HSTS queda apagado.

En cualquier entorno:

- `DATA_UPLOAD_MAX_MEMORY_SIZE` es 5 MB: un cuerpo más grande se rechaza con 400.
- `FILE_UPLOAD_MAX_MEMORY_SIZE` es 5 MB.
- `FILE_UPLOAD_PERMISSIONS = 0o644`: los archivos subidos no quedan con permisos de escritura para otros usuarios.

### Revisiones automáticas en el CI (`.github/workflows/ci.yml`)

- **`manage.py check --deploy --tag security --fail-level WARNING`**: el checklist de despliegue de Django. Falla el CI si aparece cualquier aviso de seguridad.
  - Se usa `--tag security` porque `check --deploy` también ejecuta las comprobaciones de `drf_spectacular`, que hoy dan 35 avisos sobre tipos sin anotar en la documentación Swagger. No son de seguridad.
  - Ese paso usa un `DJANGO_SECRET_KEY` aleatorio de 50+ caracteres generado en cada corrida. La clave fija del CI es corta y haría fallar `security.W009`, que se deja activo porque protege la clave real de Render.
  - Se silencia `security.W021` (`SECURE_HSTS_PRELOAD`). La lista de precarga de los navegadores solo acepta dominios propios, y el backend vive en un subdominio de `onrender.com`. Se revisa si el proyecto pasa a un dominio propio.
- **`pip-audit -r requirements.txt`**: busca vulnerabilidades conocidas en las dependencias.
  - Reportó 42 en Pillow 12.3.0, todas corregidas en 13.0.0, así que `requirements.txt` ahora pide `Pillow>=13.0,<14.0`.
  - Después del cambio no reporta ninguna.

### Pruebas

El CI corre con `DJANGO_DEBUG=False`, que activa `SECURE_SSL_REDIRECT`. Por eso
`backend/conftest.py` la apaga en las pruebas: el cliente de pruebas usa http. También vacía el
caché entre pruebas.

| Archivo | Qué prueba |
|---|---|
| `backend/tests/test_seguridad_fuerza_bruta.py` | Límite por IP, bloqueo por cuenta, registro en el log |
| `backend/tests/test_seguridad_decoradores.py` | Contraseña oculta en el reporte de errores, cabeceras `Cache-Control` |
| `backend/tests/test_seguridad_produccion.py` | Settings de producción, redirección a https y su excepción, límite de 5 MB |
