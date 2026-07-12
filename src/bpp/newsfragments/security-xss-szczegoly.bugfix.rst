Bezpieczeństwo: usunięto podatność stored XSS. Pola ``informacje``,
``szczegoly`` i ``uwagi`` rekordu (renderowane w opisie bibliograficznym)
są teraz sanityzowane przy zapisie tak jak tytuły, a etykiety globalnej
wyszukiwarki (nazwiska autorów, nazwy jednostek i źródeł) są escapowane —
nie da się już wstrzyknąć skryptu przez te pola.
