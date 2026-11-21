"""Import z PBN trafiający w rekord w koszu: POMIŃ i ZGŁOŚ (nie wskrzeszaj).

Decyzja właściciela (listopad 2026): rekord usunięty w BPP został usunięty
świadomie. Import go nie przywraca — pomija i raportuje jawnie
(``RekordWKoszuPominietyPrzezImport``, log, nieścisłość sesji importu).
Bez zajrzenia do kosza import tworzyłby duplikat (matching idzie po
``Rekord``) albo wywracał się na unikalnym ``pbn_uid``.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.models import Publication
from pbn_integrator.importer.articles import importuj_artykul
from pbn_integrator.importer.books import importuj_ksiazke
from pbn_integrator.importer.chapters import importuj_rozdzial
from pbn_integrator.models import RekordWKoszuPominietyPrzezImport

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


def _sprawdz_pominiecie(zwrocony, rekord, zrodlo_importu, model):
    """Wspólne asercje: rekord został w koszu, bez duplikatu, z raportem."""
    assert zwrocony is None, "import zwrócił rekord zamiast go pominąć"
    assert model.global_objects.count() == 1, "w bazie powstal duplikat"

    rekord.refresh_from_db()
    assert rekord.deleted_at is not None, "import wskrzesił rekord z kosza"

    wpis = RekordWKoszuPominietyPrzezImport.objects.get()
    assert wpis.object_id == rekord.pk
    assert wpis.zrodlo_importu == zrodlo_importu
    assert "ale u nas jest usunięty" in wpis.komunikat


@pytest.mark.django_db
def test_import_artykulu_pomija_rekord_z_kosza():
    publication = _publikacja("a-kosz", ARTICLE_OBJECT)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)
    wc.delete()

    assert publication.rekord_w_bpp is None, (
        "zalozenie testu: matching NIE widzi kosza (akcesory po Rekord)"
    )

    # client=None jest bezpieczne: gałąź kosza zwraca, zanim cokolwiek
    # sięgnie po PBN.
    zwrocony = importuj_artykul("a-kosz", default_jednostka=None, client=None)

    _sprawdz_pominiecie(zwrocony, wc, "articles", Wydawnictwo_Ciagle)


@pytest.mark.django_db
def test_import_ksiazki_pomija_rekord_z_kosza():
    publication = _publikacja("b-kosz", BOOK_OBJECT)
    wz = baker.make(Wydawnictwo_Zwarte, pbn_uid=publication)
    wz.delete()

    zwrocony = importuj_ksiazke("b-kosz", default_jednostka=None, client=None)

    _sprawdz_pominiecie(zwrocony, wz, "books", Wydawnictwo_Zwarte)


@pytest.mark.django_db
def test_import_rozdzialu_pomija_rekord_z_kosza():
    publication = _publikacja("c-kosz", CHAPTER_OBJECT)
    wz = baker.make(Wydawnictwo_Zwarte, pbn_uid=publication)
    wz.delete()

    zwrocony = importuj_rozdzial("c-kosz", default_jednostka=None, client=None)

    _sprawdz_pominiecie(zwrocony, wz, "chapters", Wydawnictwo_Zwarte)


@pytest.mark.django_db
def test_zywy_rekord_wraca_jako_rekord_i_nie_trafia_do_rejestru():
    """Kontrola: ścieżka bez kosza ma zostać nietknięta.

    Trafienie w ŻYWY rekord nadal zwraca obiekt ``Rekord`` (kontrakt, na którym
    stoi admin: ``isinstance(created_record, Rekord)`` → ``.original``), a
    raport kosza zostaje pusty.
    """
    from bpp.models import Rekord

    publication = _publikacja("a-zywy", ARTICLE_OBJECT)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)

    zwrocony = importuj_artykul("a-zywy", default_jednostka=None, client=None)

    assert isinstance(zwrocony, Rekord)
    assert zwrocony.pbn_uid_id == publication.pk
    assert zwrocony.original.pk == wc.pk
    assert not RekordWKoszuPominietyPrzezImport.objects.exists()


@pytest.mark.django_db
def test_pusty_kosz_idzie_dalej_do_tworzenia_nowego_rekordu(
    jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    """Kontrola negatywna: pusty kosz nie może zatrzymać importu.

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
    assert not RekordWKoszuPominietyPrzezImport.objects.exists()


@pytest.mark.django_db
def test_kolejny_import_aktualizuje_wpis_zamiast_dublowac():
    publication = _publikacja("a-dwa", ARTICLE_OBJECT)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)
    wc.delete()

    importuj_artykul("a-dwa", default_jednostka=None, client=None)
    importuj_artykul("a-dwa", default_jednostka=None, client=None)

    wpis = RekordWKoszuPominietyPrzezImport.objects.get()
    assert wpis.ile_razy == 2


@pytest.mark.django_db
def test_nieścisłość_trafia_do_raportu_sesji():
    publication = _publikacja("a-sesja", ARTICLE_OBJECT)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)
    wc.delete()
    zgloszone = []

    def callback(**kwargs):
        zgloszone.append(kwargs)

    importuj_artykul(
        "a-sesja", default_jednostka=None, client=None, inconsistency_callback=callback
    )

    assert len(zgloszone) == 1
    assert zgloszone[0]["inconsistency_type"] == "record_in_trash"
    assert zgloszone[0]["bpp_publication"].pk == wc.pk


@pytest.mark.django_db
def test_rozdzial_ksiazki_z_kosza_jest_pomijany():
    from pbn_integrator.importer.chapters import znajdz_ksiazke_nadrzedna

    ksiazka_pbn = _publikacja("ksiazka-kosz", BOOK_OBJECT)
    wz = baker.make(Wydawnictwo_Zwarte, pbn_uid=ksiazka_pbn)
    wz.delete()

    assert znajdz_ksiazke_nadrzedna("ksiazka-kosz").pk == wz.pk

    obiekt = dict(CHAPTER_OBJECT, book={"id": "ksiazka-kosz"})
    _publikacja("rozdzial-1", obiekt)
    assert importuj_rozdzial("rozdzial-1", default_jednostka=None, client=None) is None

    wpis = RekordWKoszuPominietyPrzezImport.objects.get()
    assert wpis.object_id == wz.pk
    assert wpis.zrodlo_importu == "chapters:ksiazka-nadrzedna"
    wz.refresh_from_db()
    assert wz.deleted_at is not None


def test_raport_jest_tylko_do_odczytu_w_adminie(rf, admin_user):
    from django.contrib import admin

    model_admin = admin.site._registry[RekordWKoszuPominietyPrzezImport]
    request = rf.get("/")
    request.user = admin_user
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
