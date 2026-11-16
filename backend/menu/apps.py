from django.apps import AppConfig


class MenuConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "menu"
    verbose_name = "Menu"

    def ready(self):
        from . import agotados  # noqa: F401  (registra la señal que resuelve los agotados)
