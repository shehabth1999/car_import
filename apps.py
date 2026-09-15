from django.apps import AppConfig


class CarImportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'car_import'
    verbose_name = 'Car Import'

    def ready(self):
        super().ready()
        from . import extensions  # noqa: F401
