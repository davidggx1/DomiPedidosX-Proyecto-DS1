ADMINISTRADOR = "administrador"
OPERADOR = "operador"
COCINA = "cocina"
REPARTIDOR = "repartidor"

ROLES_PERSONAL = (ADMINISTRADOR, OPERADOR, COCINA, REPARTIDOR)


def obtener_rol(usuario):
    """Devuelve el rol de personal del usuario, o None si no tiene (p. ej. un cliente)."""
    grupos = set(usuario.groups.values_list("name", flat=True))
    for rol in ROLES_PERSONAL:
        if rol in grupos:
            return rol
    return None


def obtener_sede(usuario):
    """Sede del empleado; None para el administrador o si no es empleado."""
    empleado = getattr(usuario, "empleado", None)
    return empleado.sede if empleado else None