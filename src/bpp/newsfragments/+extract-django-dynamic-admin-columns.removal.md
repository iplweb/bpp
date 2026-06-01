Aplikacja ``dynamic_columns`` została wydzielona do osobnego pakietu
``django-dynamic-columns`` (publikacja na PyPI, repo
``iplweb/django-dynamic-columns``). Z perspektywy BPP nic się nie
zmienia: konfiguracja w ``settings.DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS``
oraz ``settings.DYNAMIC_COLUMNS_FORBIDDEN_COLUMN_NAMES`` pozostaje
identyczna, a wszystkie zapisane przez użytkowników wybory kolumn w
adminie nadal działają — pakiet zachowuje te same tabele i migracje
co poprzednia, wbudowana w BPP aplikacja.
