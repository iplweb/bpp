Logi backendu Django zawierają teraz timestamp w formacie
ISO oraz nazwę loggera, co pozwala korelować zdarzenia
między równoczesnymi workerami w produkcji bez polegania
wyłącznie na timestampach z ``systemd`` / Celery. Domyślnie
skonfigurowane są też loggery ``django.security``
(SuspiciousOperation, DisallowedHost, niewłaściwy CSRF token),
``django.request`` (4xx/5xx requestów) i ``celery``
(retry, ack, errors). Dotychczasowy logger ``pbn_import``
zachowuje swój dawny czysty format (bez timestampu) na
potrzeby UI pełnotekstowego importu.
