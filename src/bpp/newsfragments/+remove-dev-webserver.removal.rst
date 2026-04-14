Usunięto dev-only serwis ``webserver`` (nginx) z ``docker-compose.yml``
oraz katalog ``docker/webserver/``. Produkcyjny nginx żyje w osobnym
repozytorium ``bpp-deploy`` (``defaults/webserver/``) i znacząco
różni się od dotychczasowej wersji lokalnej (HTTP/3 QUIC, nagłówki
bezpieczeństwa, resolver Dockera, ``/healthz``). Trzymanie dwóch
rozjechanych kopii w dwóch repo powodowało dryf konfiguracji
i fałszywe poczucie testowania prod-ready stacka lokalnie.

Lokalny development używa ``runserver`` razem z infrastrukturą
podnoszoną przez ``docker compose up db redis rabbitmq``, więc
nginx przed appserverem był nadmiarowy. Jeśli potrzebujesz
przetestować pełny stack za nginxem zgodny z produkcją, użyj
``bpp-deploy``.
