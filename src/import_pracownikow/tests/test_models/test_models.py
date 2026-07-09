import pytest
from liveops.testing import MockProgress

from bpp.models import Autor, Autor_Jednostka
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.tests.conftest import (
    import_pracownikow_factory,
    xls_path_factory,
)


def _pelny_przebieg(imp):
    """Analiza (dry-run) + integracja (commit) — odpowiednik starego
    ``.perform()``, który robił obie fazy jedną metodą (Faza 0 T7)."""
    imp.stan = ImportPracownikow.STAN_ZMAPOWANY
    imp.run(MockProgress(imp))
    imp.stan = ImportPracownikow.STAN_ZATWIERDZONY
    imp.run(MockProgress(imp))
    imp.refresh_from_db()


@pytest.mark.django_db
def test_ImportPracownikow_perform(import_pracownikow):
    _pelny_przebieg(import_pracownikow)
    assert import_pracownikow.stan == ImportPracownikow.STAN_ZINTEGROWANY
    assert import_pracownikow.importpracownikowrow_set.count() == 1
    assert import_pracownikow.importpracownikowrow_set.first().zmiany_potrzebne
    assert Autor_Jednostka.objects.count() == 1

    # Restart analizy: cofamy stan, kasujemy wiersze (on_restart), po czym
    # powtarzamy pełny przebieg — dane w bazie już odpowiadają plikowi, więc
    # tym razem żadne zmiany nie są potrzebne.
    import_pracownikow.stan = ImportPracownikow.STAN_UTWORZONY
    import_pracownikow.on_restart()
    _pelny_przebieg(import_pracownikow)
    assert not import_pracownikow.importpracownikowrow_set.first().zmiany_potrzebne


def test_ImportPracownikow_perform_aktualizacja_tytulu_nastapila(
    import_pracownikow, tytuly
):
    _pelny_przebieg(import_pracownikow)
    assert Autor.objects.get(pk=50).tytul.skrot == "lek. med."


@pytest.mark.django_db
def test_ImportPracownikow_perform_aktualizacja_tytulu_brakujacy_tytul(
    baza_importu_pracownikow, admin_user
):
    ip = import_pracownikow_factory(admin_user, xls_path_factory("_nieistn_tytul"))

    _pelny_przebieg(ip)
    assert Autor.objects.get(pk=50).tytul is None


def test_ImportPracownikow_brak_naglowka(import_pracownikow_brak_naglowka):
    """Plik bez wierszy danych — faza analizy jawnie rzuca ``ValueError``
    (Faza 0 T3), zamiast po cichu tworzyć 0 wierszy jak stare ``.perform()``."""
    with pytest.raises(ValueError, match="0 wierszy"):
        _pelny_przebieg(import_pracownikow_brak_naglowka)
    assert import_pracownikow_brak_naglowka.importpracownikowrow_set.count() == 0
