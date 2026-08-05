"""Import PBN → BPP musi POMIJAĆ rekordy strukturalnie niekompletne.

Geneza (Rollbar, batch apoz.edu.pl 2026-06-29, session_id=5): PBN zwraca
„rekordy-widma" — skasowane/wycofane albo w połowie zdenormalizowane — którym
brakuje pól niezbędnych do materializacji rekordu BPP:

- brak wersji bieżącej (``current_version is None``) → #419-podobne,
- brak ``type`` w obiekcie (``KeyError: 'type'``) → #413,
- ``CHAPTER`` bez wskazania książki nadrzędnej (``KeyError: 'book'``) → #412.

Dawniej parser indeksował te pola wprost i wywalał się KeyError-em na każdym
takim rekordzie (1133 + 61 wystąpień w jednym przebiegu — czysty szum w
Rollbarze). Bramka minimum-viable-record pomija je jawnie: liczy jako znaną
kategorię (WARNING, greppable) i zwraca ``None``, nie przerywając batcha.

Decyzja projektowa (patrz raport): pomijamy WYŁĄCZNIE braki STRUKTURALNE.
Braki opcjonalne (publisher, mainLanguage, pages, isbn) dalej degradują i
rekord się importuje — redagowane książki bez wydawcy WCHODZĄ.
"""

import pytest
from model_bakery import baker

from bpp.models import Rekord, Rodzaj_Zrodla, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.models import Publication
from pbn_integrator import importer
from pbn_integrator.importer import chapters


def _make_publication(mongo_id, obj, status="ACTIVE"):
    """Lustro ``pbn_api.Publication`` z pojedynczą bieżącą wersją i danym obiektem."""
    return baker.make(
        Publication,
        mongoId=mongo_id,
        versions=[{"current": True, "object": dict(obj)}] if obj is not None else [],
        status=status,
    )


@pytest.mark.django_db
def test_pomija_rekord_bez_type():
    """Obiekt bez ``type`` (jak #413) → None, żaden rekord BPP nie powstaje.

    client=None jest bezpieczne: bramka musi odrzucić rekord, zanim cokolwiek
    sięgnie do klienta PBN.
    """
    _make_publication("no_type", {"year": 2014, "title": "Bez typu", "volume": "X"})

    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "no_type", client=None, default_jednostka=None
    )

    assert ret is None
    assert Wydawnictwo_Ciagle.objects.count() == 0
    assert Wydawnictwo_Zwarte.objects.count() == 0
    assert Rekord.objects.filter(pbn_uid_id="no_type").count() == 0


@pytest.mark.django_db
def test_pomija_chapter_bez_book():
    """``CHAPTER`` bez ``book`` (jak #412) → None, brak rekordu."""
    _make_publication(
        "chap_no_book",
        {
            "type": "CHAPTER",
            "title": "Rozdział-sierota",
            "pagesFromTo": "91-106",
            "mainLanguage": "pol",
        },
    )

    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "chap_no_book", client=None, default_jednostka=None
    )

    assert ret is None
    assert Wydawnictwo_Zwarte.objects.count() == 0
    assert Rekord.objects.filter(pbn_uid_id="chap_no_book").count() == 0


@pytest.mark.django_db
def test_pomija_rekord_bez_current_version():
    """Brak wersji bieżącej (``versions=[]``) → None, brak rekordu."""
    _make_publication("no_ver", None)

    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "no_ver", client=None, default_jednostka=None
    )

    assert ret is None
    assert Rekord.objects.filter(pbn_uid_id="no_ver").count() == 0


@pytest.mark.django_db
def test_pomija_nieznany_type_zamiast_wywalac():
    """Nieznany, ale OBECNY ``type`` → pominięcie (nie NotImplementedError).

    Nieobsługiwany typ to dryf schematu PBN, nie awaria — batch ma lecieć dalej,
    a nie wywalać się na całym rekordzie.
    """
    _make_publication("dataset", {"type": "DATASET", "title": "Zbiór danych"})

    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "dataset", client=None, default_jednostka=None
    )

    assert ret is None
    assert Rekord.objects.filter(pbn_uid_id="dataset").count() == 0


@pytest.mark.django_db
def test_poprawny_type_jest_dispatchowany(monkeypatch):
    """Kontrola specyficzności: poprawny ``ARTICLE`` przechodzi bramkę do importu."""
    _make_publication("ok_art", {"type": "ARTICLE", "title": "OK", "year": 2020})

    wywolane = []
    monkeypatch.setattr(
        importer, "importuj_artykul", lambda mongoId, **kw: wywolane.append(mongoId)
    )

    importer.importuj_publikacje_po_pbn_uid_id(
        "ok_art", client=None, default_jednostka=None
    )

    assert wywolane == ["ok_art"]


@pytest.mark.django_db
def test_chapter_z_book_jest_dispatchowany(monkeypatch):
    """Kontrola: ``CHAPTER`` z poprawnym ``book`` przechodzi bramkę.

    Dispatch musi zaimportować książkę nadrzędną (po ``book.id``) oraz rozdział.
    """
    _make_publication(
        "ok_chap",
        {
            "type": "CHAPTER",
            "title": "Rozdział",
            "book": {"id": "parent_book"},
        },
    )

    ksiazki, rozdzialy = [], []
    monkeypatch.setattr(
        importer, "importuj_ksiazke", lambda mongoId, **kw: ksiazki.append(mongoId)
    )
    monkeypatch.setattr(
        importer, "importuj_rozdzial", lambda mongoId, **kw: rozdzialy.append(mongoId)
    )

    importer.importuj_publikacje_po_pbn_uid_id(
        "ok_chap", client=None, default_jednostka=None
    )

    assert ksiazki == ["parent_book"]
    assert rozdzialy == ["ok_chap"]


# --- Znaleziska z review (Fable): rodzic-widmo, string rekord_w_bpp,
#     przeżywalność wsadu, obserwowalność nieznanego typu ---


@pytest.mark.django_db
def test_pomija_chapter_z_widmowym_rodzicem():
    """CHAPTER poprawny, ale jego książka nadrzędna jest rekordem-widmem (W1).

    Dawniej ``importuj_ksiazke(book_id)`` dla widmowego rodzica wywalał
    ``TypeError`` na ``current_version["object"]`` i (w pętli bez try/except)
    zabijał cały wsad. Teraz rodzic-widmo jest pomijany, a cały import rozdziału
    degraduje do ``None`` bez wyjątku.
    """
    _make_publication("pb_ghost", None)  # versions=[] → current_version None
    _make_publication(
        "c_ghost_parent",
        {
            "type": "CHAPTER",
            "title": "Rozdział z rodzicem-widmem",
            "book": {"id": "pb_ghost"},
        },
    )

    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "c_ghost_parent", client=None, default_jednostka=None
    )

    assert ret is None
    assert Wydawnictwo_Zwarte.objects.count() == 0
    assert Rekord.objects.filter(pbn_uid_id="c_ghost_parent").count() == 0


@pytest.mark.django_db
def test_rozdzial_rodzic_string_pomijany(monkeypatch):
    """Książka nadrzędna rozwiązana do STRINGA (zdublowane Rekord-y) → pominięcie.

    ``rekord_w_bpp`` przy ``MultipleObjectsReturned`` zwraca join tytułów
    (string). Dawniej ``wydawnictwo_nadrzedne.rok`` wywalał ``AttributeError``
    (niedokończony fix #419). Teraz rozdział jest pomijany.
    """
    _make_publication(
        "c_str",
        {"type": "CHAPTER", "title": "Rozdział", "book": {"id": "pb_str"}},
    )
    # Brak Wydawnictwo_Zwarte dla pb_str → importuj_ksiazke wywołane; udajemy
    # że rekord_w_bpp trafił na duplikaty i zwrócił string.
    monkeypatch.setattr(
        chapters, "importuj_ksiazke", lambda *a, **k: ";; Tytuł A ;; Tytuł B"
    )

    ret = chapters.importuj_rozdzial("c_str", default_jednostka=None, client=None)

    assert ret is None


@pytest.mark.django_db
def test_instytucji_przezywa_zly_rekord(monkeypatch):
    """Pojedynczy wywalający się rekord nie zabija pętli ``importuj_..._instytucji``.

    To gwarancja „jeden zły wpis nie wywala wsadu" dla starej ścieżki batch
    (dawniej pętla nie miała żadnego try/except — W1).
    """
    _make_publication("good1", {"type": "ARTICLE", "title": "OK", "year": 2020})
    _make_publication("bad1", {"type": "ARTICLE", "title": "Zły", "year": 2020})
    Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")

    przetworzone = []

    def fake(mongoId, **kw):
        przetworzone.append(mongoId)
        if mongoId == "bad1":
            raise RuntimeError("boom")
        return None

    monkeypatch.setattr(importer, "importuj_publikacje_po_pbn_uid_id", fake)

    # nie może rzucić mimo zzłego rekordu — pętla łapie i leci dalej
    importer.importuj_publikacje_instytucji(client=None, default_jednostka=None)

    assert set(przetworzone) == {"good1", "bad1"}


@pytest.mark.django_db
def test_nieznany_type_eskaluje_inconsistency_callback():
    """Nieobsługiwany, OBECNY typ → eskalacja przez inconsistency_callback (W3).

    Widma pomijamy cicho (WARNING), ale realna zmiana schematu PBN (nowy typ)
    nie może zniknąć bez śladu — leci do kanału nieścisłości.
    """
    _make_publication("dat2", {"type": "DATASET", "title": "Zbiór danych"})

    zdarzenia = []

    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "dat2",
        client=None,
        default_jednostka=None,
        inconsistency_callback=lambda **kw: zdarzenia.append(kw),
    )

    assert ret is None
    assert len(zdarzenia) == 1
    assert zdarzenia[0]["inconsistency_type"] == "unsupported_publication_type"
