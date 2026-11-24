// Roles del sistema. Los valores coinciden con los grupos de Django
// creados por `seed_datos` y con la Tarea 3 (permisos por rol).
export const ROLES = {
  CLIENTE: 'cliente',
  OPERADOR: 'operador',
  COCINA: 'cocina',
  REPARTIDOR: 'repartidor',
  ADMINISTRADOR: 'administrador',
}

export const ETIQUETA_ROL = {
  [ROLES.CLIENTE]: 'Cliente',
  [ROLES.OPERADOR]: 'Operador de sede',
  [ROLES.COCINA]: 'Cocina',
  [ROLES.REPARTIDOR]: 'Repartidor',
  [ROLES.ADMINISTRADOR]: 'Administrador',
}

// Opciones de navegación que ve cada rol. La primera es su página de inicio.
export const ENLACES_POR_ROL = {
  [ROLES.CLIENTE]: [
    { ruta: '/menu', texto: 'Menú' },
    { ruta: '/mis-pedidos', texto: 'Mis pedidos' },
    { ruta: '/direcciones', texto: 'Mis direcciones' },
    { ruta: '/perfil', texto: 'Mi perfil' },
  ],
  [ROLES.OPERADOR]: [
    { ruta: '/operador', texto: 'Pedidos entrantes' },
    { ruta: '/operador/crear-pedido', texto: 'Crear pedido' },
    { ruta: '/operador/en-curso', texto: 'Pedidos en curso' },
    { ruta: '/operador/menu', texto: 'Categorias' },
    { ruta: '/operador/productos', texto: 'Productos' },
    { ruta: '/operador/adiciones', texto: 'Adiciones' },
    { ruta: '/operador/ingredientes', texto: 'Ingredientes' },
    { ruta: '/operador/inventario', texto: 'Inventario' },
    { ruta: '/operador/repartidores', texto: 'Repartidores' },
    { ruta: '/operador/repartidores/estado', texto: 'Estado de repartidores' },
    { ruta: '/operador/promociones', texto: 'Promociones' },
    { ruta: '/operador/combos', texto: 'Combos' },
    { ruta: '/operador/pedidos-del-dia', texto: 'Pedidos del día' },
  ],
  [ROLES.COCINA]: [
    { ruta: '/cocina', texto: 'Tablero de cocina' },
    { ruta: '/cocina/productos', texto: 'Productos' },
  ],
  [ROLES.REPARTIDOR]: [
    { ruta: '/repartidor', texto: 'Mis entregas' },
    { ruta: '/repartidor/historial', texto: 'Historial' },
  ],
  [ROLES.ADMINISTRADOR]: [
    { ruta: '/admin', texto: 'Dashboard' },
    { ruta: '/admin/pedidos', texto: 'Pedidos del día' },
    { ruta: '/admin/historial', texto: 'Historial' },
    { ruta: '/admin/reportes', texto: 'Reportes' },
    // Los horarios, festivos y franjas de capacidad se configuran desde cada sede
    { ruta: '/admin/sedes', texto: 'Sedes y horarios', activoEn: ['/admin/horarios'] },
    { ruta: '/admin/zonas', texto: 'Zonas de cobertura' },
    { ruta: '/admin/notificaciones', texto: 'Notificaciones' },
    { ruta: '/admin/personal', texto: 'Personal' },
    { ruta: '/admin/cuentas', texto: 'Cuentas' },
    { ruta: '/admin/clientes', texto: 'Clientes' },
    { ruta: '/admin/promociones', texto: 'Promociones' },
    { ruta: '/admin/combos', texto: 'Combos' },
  ],
}

export function rutaInicio(rol) {
  return ENLACES_POR_ROL[rol]?.[0]?.ruta ?? '/login'
}
