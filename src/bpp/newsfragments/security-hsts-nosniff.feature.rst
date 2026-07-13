Bezpieczeństwo: w konfiguracji produkcyjnej włączono nagłówki transportu —
``SECURE_CONTENT_TYPE_NOSNIFF``, ``SECURE_SSL_REDIRECT`` oraz HSTS
(``SECURE_HSTS_SECONDS`` = 1 rok, z ``INCLUDE_SUBDOMAINS``) jako
defense-in-depth wobec ataków typu SSL-strip/MITM i MIME-sniffing.
