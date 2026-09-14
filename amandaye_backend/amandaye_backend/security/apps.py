from django.apps import AppConfig


class SecurityConfig(AppConfig):
    name = "amandaye_backend.security"

    def ready(self):
        from . import signals  # noqa: F401
