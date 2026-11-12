from django.apps import AppConfig


class PedidosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pedidos"

    def ready(self):
        from . import alertas_capacidad, asignacion_automatica, signals  # noqa: F401
    verbose_name = "Pedidos"
