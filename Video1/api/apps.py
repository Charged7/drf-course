from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        import api.schema  # Реєструємо схему при завантаженні додатка
        from . import signals  # Імпортуємо сигнали для реєстрації обробників