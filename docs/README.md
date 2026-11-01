# Documentación de DomiPedidosX

## Estructura del backend

El backend está dividido en 6 apps de Django:

| App | Qué contiene |
|---|---|
| `sedes` | Ciudad, Sede, ZonaCobertura, CapacidadSede, HorarioSede, Feriado |
| `usuarios` | Usuario, Cliente, Empleado, Repartidor, DireccionEntrega |
| `menu` | CategoriaMenu, Producto, ProductoTamano, Insumo, Adicion, ProductoAdicion, ProductoInsumo |
| `inventario` | InventarioProducto, InventarioInsumo |
| `promociones` | Combo, ComboProducto, ComboSede |
| `pedidos` | Pedido, HistorialEstadoPedido, Factura, DetallePedido, DetallePedidoAdicion, ConsumoCupoCombo, Notificacion |

## Dependencias entre apps

Las dependencias van en un solo sentido, para evitar importaciones circulares:

- `usuarios` depende de `sedes`
- `inventario` depende de `sedes` y `menu`
- `promociones` depende de `sedes` y `menu`
- `pedidos` depende de `sedes`, `usuarios`, `menu` y `promociones`

Las relaciones entre apps se escriben como texto (`"sedes.Sede"`) y al usuario siempre se referencia con `settings.AUTH_USER_MODEL`.

## Convenciones

- Campos de los modelos en `snake_case`.
- Clave primaria automática de Django (`id`).
- Dinero en `DecimalField`.
- Estados como listas cerradas (`TextChoices`).

## Documentos

Agrega aquí los documentos del proyecto (diagrama ER, decisiones técnicas, manual de instalación).
