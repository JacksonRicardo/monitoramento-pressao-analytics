from django.apps import AppConfig


class PressaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pressao"
    verbose_name = "Controle de Pressão"

    def ready(self):
        from . import signals  # noqa: F401

