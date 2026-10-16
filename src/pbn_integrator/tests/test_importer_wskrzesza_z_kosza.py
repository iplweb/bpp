"""Import trafiający w rekord w koszu wskrzesza go, zamiast tworzyć duplikat.

Kontekst (faza 03 soft-delete, pozycja 3.1 handoffu):

Akcesory (``rekord_w_bpp``, ``get_bpp_publication``, ``matchuj_publikacje``)
NIE zaglądają do kosza — decyzja właściciela: „soft-delete znaczy, że rekordu
nie ma". Wszystkie idą po ``Rekord``, czyli po widoku odfiltrowanym po
``deleted_at``.

Skutkiem jest asymetria, która sama w sobie jest błędem importu:

- dla matchingu rekord w koszu **nie istnieje** (``rekord_w_bpp`` → ``None``),
- ale ``pbn_uid`` to ``OneToOneField(unique=True)`` **bez** warunku partial,
  więc rekord w koszu **wciąż trzyma** to pole.

Import wchodzi więc w gałąź „utwórz nowy rekord" i wywala się ``IntegrityError``
na unique ``pbn_uid_id``. Zaglądanie do kosza jest decyzją IMPORTERA (a nie
akcesora), i należy do gałęzi ``ret is None``.

Wariant A (decyzja właściciela): PBN jest źródłem prawdy — skoro publikacja
tam nadal jest, rekord wraca do BPP, a fakt ląduje w rejestrze
``RekordPrzywroconyPrzezImport``.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.models import Publication
from pbn_integrator.importer.articles import importuj_artykul
from pbn_integrator.importer.books import importuj_ksiazke
from pbn_integrator.importer.chapters import importuj_rozdzial
from pbn_integrator.models import RekordPrzywroconyPrzezImport

ARTICLE_OBJECT = {
    "type": "ARTICLE",
    "title": "Artykul, ktory wrocil z kosza",
    "year": 2023,
}

BOOK_OBJECT = {
    "type": "BOOK",
    "title": "Ksiazka, ktora wrocila z kosza",
    "year": 2023,
}

CHAPTER_OBJECT = {
    "type": "CHAPTER",
    "title": "Rozdzial, ktory wrocil z kosza",
    "year": 2023,
    "book": {"id": "nieuzywany-bo-wracamy-wczesniej"},
}


def _publikacja(mongo_id, obiekt):
    return baker.make(
        Publication,
        mongoId=mongo_id,
        versions=[{"current": True, "object": dict(obiekt)}],
        status="ACTIVE",
    )


def _sprawdz_wskrzeszenie(zwrocony, rekord, zrodlo_importu, model):
    """Wspólne asercje: ten sam wiersz wrócił, bez duplikatu, ze śladem."""
    assert zwrocony is not None, "import nie zwrocil nic — rekord z kosza zgubiony"
    assert zwrocony.pk == rekord.pk, (
        "import utworzyl NOWY rekord zamiast wskrzesic ten z kosza"
    )
    assert model.global_objects.count() == 1, "w bazie powstal duplikat"

    rekord.refresh_from_db()
    assert rekord.deleted_at is None, "rekord nie zostal wskrzeszony"

    wpis = RekordPrzywroconyPrzezImport.objects.get()
    assert wpis.object_id == rekord.pk
    assert wpis.zrodlo_importu == zrodlo_importu


@pytest.mark.django_db
def test_import_artykulu_wskrzesza_rekord_z_kosza():
    publication = _publikacja("a-kosz", ARTICLE_OBJECT)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)
    wc.delete()

    assert publication.rekord_w_bpp is None, (
        "zalozenie testu: matching NIE widzi kosza (akcesory po Rekord)"
    )

    # client=None jest bezpieczne: gałąź wskrzeszenia zwraca zanim cokolwiek
    # sięgnie po PBN.
    zwrocony = importuj_artykul("a-kosz", default_jednostka=None, client=None)

    _sprawdz_wskrzeszenie(zwrocony, wc, "articles", Wydawnictwo_Ciagle)


@pytest.mark.django_db
def test_import_ksiazki_wskrzesza_rekord_z_kosza():
    publication = _publikacja("b-kosz", BOOK_OBJECT)
    wz = baker.make(Wydawnictwo_Zwarte, pbn_uid=publication)
    wz.delete()

    zwrocony = importuj_ksiazke("b-kosz", default_jednostka=None, client=None)

    _sprawdz_wskrzeszenie(zwrocony, wz, "books", Wydawnictwo_Zwarte)


@pytest.mark.django_db
def test_import_rozdzialu_wskrzesza_rekord_z_kosza():
    publication = _publikacja("c-kosz", CHAPTER_OBJECT)
    wz = baker.make(Wydawnictwo_Zwarte, pbn_uid=publication)
    wz.delete()

    zwrocony = importuj_rozdzial("c-kosz", default_jednostka=None, client=None)

    _sprawdz_wskrzeszenie(zwrocony, wz, "chapters", Wydawnictwo_Zwarte)


@pytest.mark.django_db
def test_zywy_rekord_wraca_jako_rekord_i_nie_trafia_do_rejestru():
    """Kontrola: ścieżka bez kosza ma zostać nietknięta.

    Trafienie w ŻYWY rekord nadal zwraca obiekt ``Rekord`` (kontrakt, na którym
    stoi admin: ``isinstance(created_record, Rekord)`` → ``.original``), a
    rejestr wskrzeszeń zostaje pusty.
    """
    from bpp.models import Rekord

    publication = _publikacja("a-zywy", ARTICLE_OBJECT)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)

    zwrocony = importuj_artykul("a-zywy", default_jednostka=None, client=None)

    assert isinstance(zwrocony, Rekord)
    assert zwrocony.pbn_uid_id == publication.pk
    assert zwrocony.original.pk == wc.pk
    assert not RekordPrzywroconyPrzezImport.objects.exists()


@pytest.mark.django_db
def test_pusty_kosz_idzie_dalej_do_tworzenia_nowego_rekordu(
    jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    """Kontrola negatywna: pusty kosz nie może udawać „wskrzeszenia".

    Bez tej asercji implementacja mogłaby zatrzymać sterowanie na gałęzi kosza
    (np. zwracać coś prawdziwego, gdy nic nie znalazła) i test wskrzeszenia
    nadal by przechodził — a import przestałby cokolwiek importować.

    Ten jeden test przechodzi CAŁĄ ścieżkę tworzenia, więc potrzebuje słowników.
    Bierzemy je z fixture'ów zamiast z baseline, bo testy transakcyjne z tego
    samego przebiegu potrafią wyczyścić dane referencyjne.
    """
    from bpp.models import Rodzaj_Zrodla

    # Artykuł bez ``journal`` dostaje źródło zastępcze o tym rodzaju.
    Rodzaj_Zrodla.objects.get_or_create(nazwa="źródło nieindeksowane")

    _publikacja("a-brak", ARTICLE_OBJECT)

    zwrocony = importuj_artykul("a-brak", default_jednostka=None, client=None)

    assert isinstance(zwrocony, Wydawnictwo_Ciagle), (
        "import nie utworzyl nowego rekordu — sterowanie utknelo na koszu"
    )
    assert zwrocony.pbn_uid_id == "a-brak"
    assert not RekordPrzywroconyPrzezImport.objects.exists()
