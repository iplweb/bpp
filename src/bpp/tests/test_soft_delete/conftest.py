"""Fixtury wspólne dla testów soft-delete."""

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db.models.signals import post_migrate


@pytest.fixture
def bez_reinstalacji_denorma():
    """Odpina globalną przebudowę triggerów ``django-denorm`` na czas testu.

    PO CO: ``denorm`` podpina się pod ``post_migrate`` i po KAŻDYM
    ``migrate`` odbudowuje wszystkie swoje triggery — zawsze z AKTUALNYCH
    definicji modeli (``denorm/apps.py``:
    ``denorm_install_triggers_after_migrate``). Testy odwracalności migracji
    schodzą tymczasowo poniżej ``0496``, czyli poniżej migracji dodającej
    ``deleted_at`` na tabelach publikacji. Kolumny wtedy w bazie nie ma, ale
    modele Pythona nadal ją deklarują, więc ``denorm`` generuje bramkę
    ``WHEN (OLD."deleted_at" IS DISTINCT FROM ...)`` i ``CREATE TRIGGER``
    pada na ``UndefinedColumn``.

    DLACZEGO TO NIE JEST PROBLEM PRODUKCYJNY: w prawdziwym rollbacku
    wycofuje się KOD razem ze schematem, a stare modele nie mają
    ``deleted_at`` — ``denorm`` wygeneruje wtedy poprawne triggery.
    Kombinacja „nowy kod + stary schemat" powstaje wyłącznie tutaj, bo test
    manipuluje samym schematem, trzymając kod na miejscu.

    Po teście wpinamy handler z powrotem i odpalamy przebudowę RĘCZNIE —
    baza testowa jest współdzielona przez cały przebieg, więc nie wolno
    zostawić jej z triggerami niepasującymi do modeli.
    """
    from denorm import denorms
    from denorm.apps import denorm_install_triggers_after_migrate

    sender = apps.get_app_config("denorm")
    post_migrate.disconnect(denorm_install_triggers_after_migrate, sender=sender)
    try:
        yield
    finally:
        post_migrate.connect(denorm_install_triggers_after_migrate, sender=sender)
        # Doprowadzamy schemat z powrotem do najnowszej migracji SAMI, zamiast
        # ufać, że test zdążył to zrobić: gdy asercja padnie w połowie, test
        # przerywa przed swoim `migrate` i baza zostaje w stanie sprzed
        # docelowej migracji. Wywołanie jest idempotentne (no-op, gdy już
        # jesteśmy na szczycie), a bez niego przebudowa niżej wywaliłaby się
        # na brakującej kolumnie, przykrywając PRAWDZIWY powód porażki testu.
        call_command("migrate", "bpp", verbosity=0)
        denorms.install_triggers()
