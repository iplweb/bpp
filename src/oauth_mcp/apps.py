from django.apps import AppConfig


class OauthMcpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "oauth_mcp"

    def ready(self):
        from oauth_mcp import signals  # noqa: F401  (rejestruje receivery)
