import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowOdpiecie
from import_pracownikow.pipeline.analyze import analizuj


@pytest.mark.django_db
def test_on_restart_kasuje_odpiecia():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    aj = baker.make(Autor_Jednostka)
    ImportPracownikowOdpiecie.objects.create(parent=imp, autor_jednostka=aj)
    imp.on_restart()
    assert imp.odpiecia.count() == 0


@pytest.mark.django_db
def test_analiza_materializuje_odpiecia_i_liczy(
    import_pracownikow, autor_spoza_pliku, jednostka_spoza_pliku
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)
    aj_spoza = autor_spoza_pliku.autor_jednostka_set.get(
        jednostka=jednostka_spoza_pliku
    )

    import_pracownikow.stan = ImportPracownikow.STAN_ZMAPOWANY
    p = MockProgress(import_pracownikow)
    analizuj(import_pracownikow, p)

    assert import_pracownikow.odpiecia.filter(autor_jednostka=aj_spoza).exists()
    assert all(not o.zaznaczone for o in import_pracownikow.odpiecia.all())
    assert p.result_context["odpiecia"] >= 1


@pytest.mark.django_db
def test_reanaliza_nie_duplikuje_odpiec(
    import_pracownikow, autor_spoza_pliku, jednostka_spoza_pliku
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)

    import_pracownikow.stan = ImportPracownikow.STAN_ZMAPOWANY
    analizuj(import_pracownikow, MockProgress(import_pracownikow))
    liczba1 = import_pracownikow.odpiecia.count()
    assert liczba1 >= 1

    # ponowna analiza: cofnięcie do zmapowany kasuje wiersze+odpiecia, potem
    # analiza tworzy je od nowa — bez duplikacji.
    import_pracownikow.stan = ImportPracownikow.STAN_ZMAPOWANY
    import_pracownikow.on_restart()
    analizuj(import_pracownikow, MockProgress(import_pracownikow))
    assert import_pracownikow.odpiecia.count() == liczba1
