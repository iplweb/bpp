from django.apps import AppConfig, apps


class OidcIntegrationConfig(AppConfig):
    name = "oidc_integration"
    verbose_name = "Integracja z OpenID Connect (Keycloak)"

    def ready(self):
        # Gdy easyaudit jest aktywny, jego receiver user_login_failed wywala
        # KeyError('username') na nieudanym logowaniu OAuth (callback OIDC nie
        # podaje username w credentials) — podmieniamy go na odporny wariant.
        if not apps.is_installed("easyaudit"):
            return
        from oidc_integration.easyaudit_compat import (
            install_easyaudit_login_failed_guard,
        )

        install_easyaudit_login_failed_guard()
