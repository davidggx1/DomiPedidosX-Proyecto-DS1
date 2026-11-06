from django.apps import AppConfig


class PedidosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pedidos"
    verbose_name = "Pedidos"

    def ready(self):
        # Registra el puente que publica los cambios de la máquina de estados.
        from . import signals  # noqa: F401
