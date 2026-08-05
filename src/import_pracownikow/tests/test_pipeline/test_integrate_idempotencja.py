"""#508 F2: dwukrotny commit (restart / podwójne „Zatwierdź") musi być
idempotentny.

``integrate.integruj`` nie zeruje ``zmiany_potrzebne`` ani ``diff_do_utworzenia``
po integracji wiersza, a ``ZatwierdzImportView`` / ``RestartView`` pozwalają
uruchomić fazę integracji ponownie na tym samym parencie (stan zatwierdzony/
zintegrowany NIE kasuje wierszy podglądu). Bez guardu drugi przebieg:

  * dla wiersza czysto aktualizującego (drift zaaplikowany w 1. przebiegu) —
    świeży ``check_if_integration_needed()`` zwraca już False → wiersz jest
    fałszywie oznaczany ``pominiety_bo_nieaktualny`` i licznik ``zintegrowano``
    maleje;
  * dla wiersza materializującego create'y — wpada w gałąź „materializowano"
    i NADPISUJE ``log_zmian`` (realny audyt zmian Autor_Jednostka ginie).

Guard: ``_integruj_wiersz`` pomija wiersz już zintegrowany (``log_zmian is not
None``) — ``log_zmian`` ustawia wyłącznie integracja, analiza zostawia je None.
"""

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka, Funkcja_Autora
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj


def _ponow_commit(imp):
    """Symuluje restart fazy integracji: stan wraca na ZATWIERDZONY (jak po
    ``ZatwierdzImportView``/``RestartView``), wiersze podglądu NIE są kasowane."""
    imp.stan = ImportPracownikow.STAN_ZATWIERDZONY
    imp.save(update_fields=["stan"])


def _funkcja_asystent():
    """Funkcja_Autora „asystent" — z baseline, a gdy sąsiedni test w xdist
    wyczyścił dane referencyjne (TRUNCATE CASCADE w teardownie), tworzy własną.
    Bez tego samo ``.get(nazwa="asystent")`` jest flaky pod równoległym runnerem
    (ambient-data): przechodzi w izolacji, pada w niektórych układach shardów."""
    return Funkcja_Autora.objects.filter(nazwa="asystent").first() or baker.make(
        Funkcja_Autora, nazwa="asystent"
    )


@pytest.mark.django_db
def test_dwukrotny_commit_nie_falszuje_pominiety_bo_nieaktualny(
    autor_jednostka_fixture,
):
    # Wiersz czysto aktualizujący: AJ istnieje z funkcja=None, wiersz ustawia
    # funkcja_autora=asystent (istniejący FK → diff pusty, materializowano=False).
    autor, jednostka = autor_jednostka_fixture
    funkcja = _funkcja_asystent()
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka, funkcja=None)
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
    aj.refresh_from_db()
    assert aj.funkcja == funkcja
    assert row.pominiety_bo_nieaktualny is False
    log_po_pierwszym = row.log_zmian
    assert log_po_pierwszym is not None
    assert any("funkcja" in x for x in log_po_pierwszym["autor_jednostka"])

    # Drugi commit (restart) — NIE wolno fałszywie oznaczyć wiersza jako
    # nieaktualnego ani ruszyć audytu; licznik zintegrowano ma być stabilny.
    _ponow_commit(imp)
    p2 = MockProgress(imp)
    integruj(imp, p2)
    row.refresh_from_db()
    assert row.pominiety_bo_nieaktualny is False
    assert row.log_zmian == log_po_pierwszym
    assert p2.result_context["zintegrowano"] == 1
    assert p2.result_context["pominieto_nieaktualne"] == 0


@pytest.mark.django_db
def test_dwukrotny_commit_nie_nadpisuje_log_zmian_audytu(autor_jednostka_fixture):
    # Wiersz z prawdziwym driftem AJ (funkcja=None → asystent), materializowany
    # z istniejącego FK: 1. przebieg zapisuje realny ślad w log_zmian.
    autor, jednostka = autor_jednostka_fixture
    funkcja = _funkcja_asystent()
    aj = baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka, funkcja=None)
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
        diff_do_utworzenia={"funkcja_autora": "asystent"},
        zmiany_potrzebne=True,
    )

    integruj(imp, MockProgress(imp))
    row.refresh_from_db()
    log_po_pierwszym = row.log_zmian
    assert log_po_pierwszym is not None
    assert any("funkcja" in x for x in log_po_pierwszym["autor_jednostka"])

    # Drugi commit — realny audyt zmian Autor_Jednostka NIE może zostać
    # wymazany przez ponowne wejście w gałąź „materializowano".
    _ponow_commit(imp)
    integruj(imp, MockProgress(imp))
    row.refresh_from_db()
    assert row.log_zmian == log_po_pierwszym
