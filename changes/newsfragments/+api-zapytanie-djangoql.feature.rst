Dodano autoryzowane wyszukiwanie DjangoQL po API: ``GET /api/v1/zapytanie/rekord/``,
``/zapytanie/autor/`` i ``/zapytanie/autorzy/`` (parametr ``q``), dostępne dla
zalogowanych redaktorów (staff w grupie „wprowadzanie danych") oraz przez token
MCP. Wyniki kompaktowe, stronicowane, read-only.
