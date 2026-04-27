Naprawiono błąd teardown testów ``TransactionTestCase`` (m.in. testów
Playwright z ``transaction=True``) — ``TRUNCATE`` Django flush'a wywalał
się na FK z niezarządzanej tabeli ``bpp_rekord_mat`` do zarządzanej
``bpp_charakter_formalny``. Monkey-patch ``_fixture_teardown`` (dodający
``allow_cascade=True`` i retry przy deadlocku) został przeniesiony z
``src/fixtures/conftest.py`` do ``src/conftest.py``: ten pierwszy plik
jest siostrzanym katalogiem względem testów i pytest go automatycznie
NIE ładuje dla testów spoza ``src/fixtures/``, więc patch nigdy nie
zaczepiał się dla większości testów transakcyjnych.
