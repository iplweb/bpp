Przeniesiono rejestrację generatorów ``model_bakery`` dla
``ArrayField`` i ``SearchVectorField`` z imperatywnego
``setup_model_bakery()`` do deklaratywnego
``BAKER_CUSTOM_FIELDS_GEN`` w ``django_bpp.settings.base``. Dzięki
temu generatory są znane od startu Django, niezależnie od kolejności
ładowania plików ``conftest.py`` — eliminuje sporadyczne
``TypeError: field search type <SearchVectorField> is not supported
by baker`` w testach uruchamianych bez załadowanego
``src/fixtures/conftest.py``.
