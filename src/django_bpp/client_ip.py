"""Ekstrakcja IP klienta zza reverse-proxy (nginx) dla django-axes.

Podpinane przez ``AXES_CLIENT_IP_CALLABLE`` — axes woła ``get_client_ip(request)``
przy każdej próbie logowania, żeby wyznaczyć komponent ``ip_address`` lockoutu.

Dlaczego własna funkcja zamiast django-ipware:

W deploymencie BPP (bpp-deploy) nginx jest BRZEGIEM (terminuje TLS, publikuje
80/443), a appserver/authserver nie są wystawione na hosta — cały ruch wchodzi
przez nginx, który ustawia::

    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

``$proxy_add_x_forwarded_for`` = ``<XFF od klienta>, <remote_addr>``. nginx zawsze
DOKLEJA realny ``$remote_addr`` (faktyczny TCP-peer) na KOŃCU listy. Dlatego
prawdziwym IP klienta jest OSTATNI (najbardziej prawy) wpis — i tylko on, bo
wszystko po lewej przysłał (i mógł sfałszować) klient. Standardowy ipware domyślnie
ufa wpisowi NAJBARDZIEJ LEWEMU, więc bez dokładnej konfiguracji ufałby wartości
sterowanej przez atakującego. Czytanie prawego wpisu jest tu niefalsyfikowalne
i nie wymaga dodatkowej zależności.

Bez tego axes używa ``REMOTE_ADDR`` = IP nginxa → wszyscy klienci mają to samo IP
i komponent ``ip_address`` w ``AXES_LOCKOUT_PARAMETERS`` traci sens.
"""

from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str | None:
    """Zwróć realne IP klienta: ostatni niepusty wpis X-Forwarded-For
    (doklejony przez nginx z ``$remote_addr``), a w razie braku — ``REMOTE_ADDR``.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    parts = [ip.strip() for ip in forwarded.split(",")]
    rightmost = next((ip for ip in reversed(parts) if ip), None)
    return rightmost or request.META.get("REMOTE_ADDR")
