import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka, Funkcja_Autora, Grupa_Pracownicza, Wymiar_Etatu
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj


@pytest.mark.django_db
def test_commit_materializuje_odroczone_create(autor_jednostka_fixture):
    """Wiersz create-only (odroczone create'y w ``diff_do_utworzenia``, bez
    prawdziwego "driftu" na Autor/Autor_Jednostka) MUSI zostać rozpoznany
    jako faktycznie przetworzony: NIE ``pominiety_bo_nieaktualny`` i z
    czytelnym śladem w ``log_zmian`` — inaczej licznik ``zintegrowano`` i
    audyt gubią fakt, że powstały nowe Funkcja_Autora/Autor_Jednostka
    (regresja opisana w Task 4 review)."""
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
    p = MockProgress(imp)
    integruj(imp, p)
    row.refresh_from_db()
    assert row.funkcja_autora is not None
    # "asystent" jest w danych referencyjnych (baseline) — get_or_create go
    # znajduje, nie tworzy drugi raz.
    assert Funkcja_Autora.objects.get(nazwa="asystent") == row.funkcja_autora
    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).exists()

    # Sedno fixu: create-only NIE jest "nieaktualny", a jego praca jest
    # odnotowana w log_zmian (audyt) i policzona w zintegrowano (licznik).
    assert row.pominiety_bo_nieaktualny is False
    assert row.log_zmian is not None
    assert row.log_zmian["utworzono"] == [
        "funkcja: asystent",
        "powiązanie autor-jednostka",
    ]

    # ...i licznik `zintegrowano` w wyniku fazy również widzi tę pracę
    # (wcześniej liczony przez `log_zmian__isnull=False`, co dla tej
    # ścieżki dawało błędne 0).
    assert p.result_context["zintegrowano"] == 1
    assert p.result_context["pominieto_nieaktualne"] == 0

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
def test_commit_materializuje_grupe_i_wymiar_etatu(autor_jednostka_fixture):
    """diff_do_utworzenia z odroczonymi ``grupa_pracownicza``/``wymiar_etatu``
    (obok już istniejącego ``Autor_Jednostka``) — commit musi utworzyć oba
    obiekty (get_or_create), podpiąć FK na wierszu ORAZ na
    ``Autor_Jednostka`` przez ``row.integrate()``. Tu drift jest prawdziwy
    (AJ miało ``grupa_pracownicza``/``wymiar_etatu`` puste, diff ustawia
    wartości) — ``check_if_integration_needed()`` zwraca True, więc to
    ćwiczy ścieżkę "materializowano + integrate()", różną od czystego
    create-only z testu wyżej."""
    autor, jednostka = autor_jednostka_fixture
    funkcja = Funkcja_Autora.objects.get(nazwa="asystent")
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        funkcja=funkcja,
        grupa_pracownicza=None,
        wymiar_etatu=None,
    )
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
        diff_do_utworzenia={
            "grupa_pracownicza": "nauczyciele",
            "wymiar_etatu": "pełny etat",
        },
        zmiany_potrzebne=True,
    )

    integruj(imp, MockProgress(imp))

    row.refresh_from_db()
    aj.refresh_from_db()

    grupa = Grupa_Pracownicza.objects.get(nazwa="nauczyciele")
    wymiar = Wymiar_Etatu.objects.get(nazwa="pełny etat")
    assert row.grupa_pracownicza == grupa
    assert row.wymiar_etatu == wymiar
    # FK musi wylądować na docelowym Autor_Jednostka, nie tylko na wierszu
    # importu — to properties integrate() aplikuje na model docelowy.
    assert aj.grupa_pracownicza == grupa
    assert aj.wymiar_etatu == wymiar

    # Drift jest prawdziwy (AJ nie miało grupy/wymiaru) -> integrate()
    # faktycznie się wykonał, nie ścieżka create-only.
    assert row.pominiety_bo_nieaktualny is False
    assert row.log_zmian is not None
    assert any("grupa_pracownicza" in x for x in row.log_zmian["autor_jednostka"])
    assert any("wymiar_etatu" in x for x in row.log_zmian["autor_jednostka"])
    assert row.log_zmian["utworzono"] == [
        "grupa pracownicza: nauczyciele",
        "wymiar etatu: pełny etat",
    ]

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

    p = MockProgress(imp)
    integruj(imp, p)

    row.refresh_from_db()
    assert row.pominiety_bo_nieaktualny is True
    assert row.log_zmian is None
    assert p.result_context["zintegrowano"] == 0
    assert p.result_context["pominieto_nieaktualne"] == 1
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
