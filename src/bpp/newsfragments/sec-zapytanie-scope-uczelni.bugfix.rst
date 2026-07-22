Endpoint ``/api/v1/zapytanie/`` (rekord/autor/autorzy) respektuje teraz tę
samą politykę widoczności co ``/api/v1/szukaj/``: izolację uczelni w trybie
multi-host, ukryte statusy korekty oraz rekordy oznaczone
``nie_eksportuj_przez_api``. Wcześniej autoryzowane zapytanie DjangoQL mogło
zwrócić rekordy i autorów spoza uczelni oglądającego.
