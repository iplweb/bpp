"""Masowy „Import z PBN” bierze wersję przypiętą na profilu instytucji (FD#511).

Wersję bieżącą w repozytorium PBN może zmienić ktoś spoza uczelni; uczelnia
zatwierdza (przypina) konkretną wersję na swoim profilu i to z niej ma
powstać rekord BPP.
"""

from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Rodzaj_Zrodla, Uczelnia, Wydawnictwo_Zwarte
from pbn_api.models import Institution, Publication, PublikacjaInstytucji, Scientist
from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.publication_import import PublicationImporter
from pbn_integrator import importer as integrator_importer
from pbn_integrator.importer import cache

pytestmark = pytest.mark.django_db

PRZYPIETA = "11111111-1111-1111-1111-111111111111"
BIEZACA = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def slowniki(
    jezyki, charaktery_formalne, typy_kbn, typy_odpowiedzialnosci, statusy_korekt
):
    # Importer trzyma słowniki w lru_cache na cały proces — po odtworzeniu
    # słowników przez inny test miałby stare klucze.
    cache.clear_cache()
    Rodzaj_Zrodla.objects.get_or_create(nazwa="periodyk")
    yield
    cache.clear_cache()


@pytest.fixture
def uczelnia():
    return baker.make(Uczelnia, pbn_uid=baker.make(Institution))


@pytest.fixture
def krok_importu(uczelnia, django_user_model):
    session = baker.make(ImportSession, user=baker.make(django_user_model), config={})
    client = MagicMock()
    client.uczelnia = uczelnia
    krok = PublicationImporter(session, client=client, uczelnia=uczelnia)
    krok.default_jednostka = baker.make(Jednostka, uczelnia=uczelnia)
    return krok


def _ksiazka(pbn_uid="pbn-ksiazka"):
    """Publikacja z dwiema wersjami: starszą (zatwierdzoną) i bieżącą."""
    return baker.make(
        Publication,
        mongoId=pbn_uid,
        status="ACTIVE",
        versions=[
            {
                "versionHash": PRZYPIETA,
                "object": {
                    "type": "BOOK",
                    "title": "Tytuł zatwierdzony przez uczelnię",
                    "year": 2024,
                },
            },
            {
                "current": True,
                "versionHash": BIEZACA,
                "object": {
                    "type": "BOOK",
                    "title": "Tytuł zmieniony przez kogoś obcego",
                    "year": 2024,
                },
            },
        ],
    )


def _na_profilu(uczelnia, publikacja, wersja, instytucja=None):
    return baker.make(
        PublikacjaInstytucji,
        institutionId=instytucja or uczelnia.pbn_uid,
        publicationId=publikacja,
        insPersonId=baker.make(Scientist),
        publicationVersion=wersja,
    )


def _tytul(pbn_uid="pbn-ksiazka"):
    return Wydawnictwo_Zwarte.objects.get(pbn_uid_id=pbn_uid).tytul_oryginalny


def _log(krok):
    return list(
        ImportLog.objects.filter(session=krok.session, message__contains="profilu")
    )


def test_import_masowy_tworzy_rekord_z_wersji_przypietej(krok_importu, uczelnia):
    _na_profilu(uczelnia, _ksiazka(), PRZYPIETA)

    krok_importu._import_publications_with_cancellation()

    assert _tytul() == "Tytuł zatwierdzony przez uczelnię"
    (wpis,) = _log(krok_importu)
    assert wpis.level == "info"
    assert "1 wzięto z wersji przypiętej" in wpis.message


def test_brak_wersji_przypietej_bierze_biezaca_i_ostrzega(krok_importu, uczelnia):
    _na_profilu(uczelnia, _ksiazka(), None)

    krok_importu._import_publications_with_cancellation()

    assert _tytul() == "Tytuł zmieniony przez kogoś obcego"
    (wpis,) = _log(krok_importu)
    assert wpis.level == "warning"
    assert "pbn-ksiazka" in wpis.message
    assert list(wpis.details["wersja_biezaca_zamiast_przypietej"]) == ["pbn-ksiazka"]


def test_przypieta_wersja_ktorej_nie_ma_w_kopii_bierze_biezaca_i_ostrzega(
    krok_importu, uczelnia
):
    _na_profilu(uczelnia, _ksiazka(), "33333333-3333-3333-3333-333333333333")

    krok_importu._import_publications_with_cancellation()

    assert _tytul() == "Tytuł zmieniony przez kogoś obcego"
    assert _log(krok_importu)[0].level == "warning"


def test_straznik_praca_spoza_profilu_importuje_sie_jak_dotad(krok_importu, uczelnia):
    """Bez wpisu na profilu tej uczelni: wersja bieżąca i żadnych uwag
    w logu — dokładnie jak przed zmianą."""
    _ksiazka()

    krok_importu._import_publications_with_cancellation()

    assert _tytul() == "Tytuł zmieniony przez kogoś obcego"
    assert _log(krok_importu) == []


def test_wersja_przypieta_przez_inna_instytucje_nie_dotyczy_tej_uczelni(
    krok_importu, uczelnia
):
    """Multi-hosted: liczy się profil uczelni, dla której biegnie import."""
    _na_profilu(uczelnia, _ksiazka(), PRZYPIETA, instytucja=baker.make(Institution))

    krok_importu._import_publications_with_cancellation()

    assert _tytul() == "Tytuł zmieniony przez kogoś obcego"
    assert _log(krok_importu) == []


def test_import_spoza_sesji_tez_bierze_wersje_przypieta(uczelnia, caplog):
    """``importuj_publikacje_instytucji`` (komendy, import oświadczeń)."""
    _na_profilu(uczelnia, _ksiazka(), PRZYPIETA)
    _na_profilu(uczelnia, _ksiazka("pbn-bez-przypietej"), None)
    client = MagicMock()
    client.uczelnia = uczelnia

    with caplog.at_level("WARNING", logger="pbn_integrator.importer"):
        integrator_importer.importuj_publikacje_instytucji(
            client=client, default_jednostka=None
        )

    assert _tytul() == "Tytuł zatwierdzony przez uczelnię"
    assert _tytul("pbn-bez-przypietej") == "Tytuł zmieniony przez kogoś obcego"
    assert "pbn-bez-przypietej" in caplog.text
