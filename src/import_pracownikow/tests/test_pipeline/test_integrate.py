import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka, Funkcja_Autora
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_commit_materializuje_odroczone_create(autor_jednostka_fixture):
    autor, jednostka = autor_jednostka_fixture
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=None,
        funkcja_autora=None,
        grupa_pracownicza=None,
        wymiar_etatu=None,
        tytul=None,
        dane_znormalizowane={"stanowisko": "Asystent"},
        diff_do_utworzenia={
            "funkcja_autora": "asystent",
            "autor_jednostka": {"autor": autor.pk, "jednostka": jednostka.pk},
        },
        zmiany_potrzebne=True,
    )
    integruj(imp, MockProgress(imp))
    row.refresh_from_db()
    assert row.funkcja_autora is not None
    assert Funkcja_Autora.objects.filter(nazwa__iexact="asystent").exists()
    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).exists()
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY


@pytest.mark.django_db
def test_commit_materializacja_jest_idempotentna_dla_duplikatu_osoby(
    autor_jednostka_fixture,
):
    """Dwa wiersze tego samego pliku (duplikat osoby) odkładają ten sam
    ``diff_do_utworzenia["funkcja_autora"]``/``["autor_jednostka"]`` — commit
    obu MUSI wyprodukować dokładnie jeden ``Funkcja_Autora`` i jeden
    ``Autor_Jednostka`` (get_or_create), a nie IntegrityError na duplikacie."""
    autor, jednostka = autor_jednostka_fixture
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    diff = {
        "funkcja_autora": "asystent",
        "autor_jednostka": {"autor": autor.pk, "jednostka": jednostka.pk},
    }
    for _ in range(2):
        ImportPracownikowRow.objects.create(
            parent=imp,
            autor=autor,
            jednostka=jednostka,
            autor_jednostka=None,
            funkcja_autora=None,
            grupa_pracownicza=None,
            wymiar_etatu=None,
            tytul=None,
            dane_znormalizowane={"stanowisko": "Asystent"},
            diff_do_utworzenia=diff,
            zmiany_potrzebne=True,
        )

    integruj(imp, MockProgress(imp))

    assert Funkcja_Autora.objects.filter(nazwa__iexact="asystent").count() == 1
    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 1
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY


@pytest.mark.django_db
def test_commit_pomija_wiersz_gdy_recheck_nieaktualny(autor_jednostka_fixture):
    """Między analizą (dry-run) a commitem baza mogła się zmienić: wiersz
    oznaczony w analizie jako ``zmiany_potrzebne=True`` może przy commicie
    okazać się nieaktualny (świeży ``check_if_integration_needed()`` zwraca
    False, bo docelowe wartości już są ustawione). Taki wiersz jest
    pomijany (``pominiety_bo_nieaktualny=True``) i NIE trafia do
    ``row.integrate()`` — ``log_zmian`` pozostaje puste."""
    autor, jednostka = autor_jednostka_fixture
    # "asystent" jest w danych referencyjnych (baseline) — używamy istniejącego
    # wpisu zamiast tworzyć nowy (uniqueness na "nazwa").
    funkcja = Funkcja_Autora.objects.get(nazwa="asystent")
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka, funkcja=funkcja)
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        funkcja_autora=funkcja,
        grupa_pracownicza=None,
        wymiar_etatu=None,
        tytul=None,
        dane_znormalizowane={"stanowisko": "Asystent"},
        diff_do_utworzenia={},
        zmiany_potrzebne=True,
    )

    integruj(imp, MockProgress(imp))

    row.refresh_from_db()
    assert row.pominiety_bo_nieaktualny is True
    assert row.log_zmian is None
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
