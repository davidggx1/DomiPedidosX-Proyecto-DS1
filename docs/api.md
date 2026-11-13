# Documentación de la API

La API se documenta sola a partir del código con **drf-spectacular**. Con el backend corriendo (`python backend/manage.py runserver`):

| Qué | Dónde |
|---|---|
| Swagger (probar los endpoints desde el navegador) | http://127.0.0.1:8000/api/docs/ |
| Esquema OpenAPI 3 (para Postman u otras herramientas) | http://127.0.0.1:8000/api/schema/ |

Los endpoints están agrupados por etiquetas. Las de reglas de negocio son:

| Etiqueta | Endpoints | Historias |
|---|---|---|
| **Cobertura** | `/api/zonas-cobertura/`, `POST /api/sedes/validar-cobertura/` | HU-55, HU-56, HU-57, HU-58 |
| **Capacidad** | `/api/capacidades/`, `GET /api/pedidos/capacidad/` | HU-59, HU-60, HU-61 |
| **Clientes** | `GET /api/usuarios/clientes/`, `GET /api/usuarios/clientes/{id}/` | HU-69 |

Cada uno tiene un resumen, las reglas de validación, los códigos de error posibles y ejemplos de petición y respuesta.

## Usar Swagger con un usuario

La mayoría de endpoints exigen iniciar sesión. Pedir el token **no basta**: hay que dárselo a Swagger.

1. En **`POST /api/auth/token/`** pulsa **Try it out**, escribe el correo y la contraseña y pulsa **Execute**:

   ```json
   { "email": "admin@domipedidosx.local", "password": "AdminLocal#2026" }
   ```

2. En la respuesta, copia solo el valor de **`access`** (no el `refresh`), sin las comillas.
3. Arriba de la página pulsa **Authorize**, pégalo en *jwtAuth* **sin escribir "Bearer"** y pulsa **Authorize → Close**. Los candados de los endpoints quedan cerrados.
4. Ya puedes usar los demás endpoints. El token se conserva aunque recargues la página.

Si un endpoint responde **401**, el token no se envió o ya venció (dura pocos minutos): repite los pasos 1 a 3.
Si responde **403**, el usuario no tiene el rol que el endpoint exige (por ejemplo, zonas y franjas son solo para el administrador).

> En los endpoints con `{id}` se usa el **id numérico** del registro (el de la URL en el frontend, por ejemplo `/repartidor/entregas/8`), no el número de pedido `P-…`.

## Importar la API en Postman

1. Con el backend corriendo, en Postman pulsa **Import → Link** y pega `http://127.0.0.1:8000/api/schema/`.
2. Elige **Postman Collection** y confirma. Se crea una colección con todas las carpetas y ejemplos.
3. Para autenticarte: haz la petición `POST /api/auth/token/` de la colección, copia el `access`, abre la colección → pestaña **Authorization** → tipo **Bearer Token** y pégalo. Todas las peticiones lo heredan.

Cuando cambie la API, vuelve a importar el enlace para actualizar la colección.

## Mantener la documentación

- Si una vista arma su respuesta con un diccionario, documenta su forma con un serializer de solo lectura (ver `sedes/esquemas.py` y `EstadoCapacidadSerializer` en `pedidos/capacidad.py`) y úsalo en `@extend_schema(responses=...)`.
- Los `SerializerMethodField` necesitan el tipo de retorno (`-> bool`, `-> str`) o `@extend_schema_field`; si no, Swagger los muestra como texto.
- Para revisar advertencias: `python backend/manage.py spectacular --validate --file schema.yaml`.
- `tests/test_documentacion_api.py` falla si la documentación de cobertura, capacidad o clientes deja de corresponder con lo que hace la API.
