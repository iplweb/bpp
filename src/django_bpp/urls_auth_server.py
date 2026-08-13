"""Minimal URL configuration for auth server.

Serwis obsługuje SSO do narzędzi administracyjnych stojących za nginksowym
``auth_request`` (Grafana, Dozzle, Flower, Netdata). Nie jest to tryb awaryjny
ani "zapasowe" logowanie — to normalna ścieżka wejścia do tych narzędzi; osobny
proces istnieje po to, żeby wstawał w sekundach i nie zależał od pełnej
aplikacji.

Endpointy:
- /__external_auth/is_superuser/ - podzapytanie autoryzacyjne dla nginksa
- /__external_auth/login/        - formularz logowania (nginx: error_page 401)
- /__external_auth/forbidden/    - "brak uprawnień" (nginx: error_page 403)
- /__external_auth/logout/       - wylogowanie ze strony "brak uprawnień"
- /health/                       - health check dla Dockera / load balancera
"""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from django_bpp.health import health_check
from django_bpp.views import brak_uprawnien, is_superuser

urlpatterns = [
    path("__external_auth/is_superuser/", is_superuser, name="is_superuser"),
    path(
        "__external_auth/login/",
        LoginView.as_view(template_name="auth_server/login.html"),
        name="login",
    ),
    path("__external_auth/forbidden/", brak_uprawnien, name="forbidden"),
    path(
        "__external_auth/logout/",
        # ``next_page`` wprost, a nie przez settings.LOGIN_URL: po wylogowaniu
        # użytkownik ma wrócić na formularz TEGO serwisu, niezależnie od tego,
        # czym akurat jest LOGIN_URL w załadowanych ustawieniach.
        LogoutView.as_view(next_page="/__external_auth/login/"),
        name="logout",
    ),
    path("health/", health_check, name="health"),
]
