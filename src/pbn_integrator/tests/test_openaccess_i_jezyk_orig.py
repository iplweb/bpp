"""Odporność importera PBN na niekompletne dane Open Access oraz round-trip
języka oryginalnego (``originalLanguage`` → ``jezyk_orig``).

- ``importuj_openaccess`` — blok ``openAccess`` z PBN bywa niekompletny (potrafi
  nie zawierać ``mode``/``license``/``releaseDateMode``/``textVersion``).
  Wszystkie docelowe pola FK są nullable, więc brak klucza ma zostawić pole
  puste, a nie wywalić import ``KeyError``-em.
- ``ustaw_jezyk_oryginalny`` — adapter eksportu zapisuje ``originalLanguage`` z
  ``jezyk_orig``; importer musi go odczytać z powrotem (inaczej leftover wywala
  ``assert_dictionary_empty``).
"""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Tryb_OpenAccess_Wydawnictwo_Ciagle
from pbn_integrator.importer.helpers import (
    importuj_openaccess,
    ustaw_jezyk_oryginalny,
)


@pytest.fixture
def wydawnictwo_ciagle(db):
    return baker.make("bpp.Wydawnictwo_Ciagle", adnotacje="", tytul="")


class TestImportujOpenaccess:
    def test_komplet_ustawia_wszystkie_pola(self, wydawnictwo_ciagle):
        # Skróty syntetyczne (nieobecne w baseline), by nie kolidować z
        # ograniczeniem unikalności słowników OA.
        baker.make("bpp.Licencja_OpenAccess", skrot="TST-LIC")
        baker.make("bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle", skrot="TST_TRYB")
        baker.make("bpp.Czas_Udostepnienia_OpenAccess", skrot="TST_CZAS")
        baker.make("bpp.Wersja_Tekstu_OpenAccess", skrot="TST_WERSJA")

        pbn_json = {
            "openAccess": {
                "license": "TST_LIC",
                "mode": "TST_TRYB",
                "releaseDateMode": "TST_CZAS",
                "textVersion": "TST_WERSJA",
            }
        }

        importuj_openaccess(
            wydawnictwo_ciagle,
            pbn_json,
            klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
        )

        assert wydawnictwo_ciagle.openaccess_licencja.skrot == "TST-LIC"
        assert wydawnictwo_ciagle.openaccess_tryb_dostepu.skrot == "TST_TRYB"
        assert wydawnictwo_ciagle.openaccess_czas_publikacji.skrot == "TST_CZAS"
        assert wydawnictwo_ciagle.openaccess_wersja_tekstu.skrot == "TST_WERSJA"
        assert pbn_json == {}

    def test_bez_mode_nie_wywala_importu(self, wydawnictwo_ciagle):
        # wcześniej: KeyError 'mode'
        baker.make("bpp.Licencja_OpenAccess", skrot="TST-LIC")

        pbn_json = {"openAccess": {"license": "TST_LIC"}}

        importuj_openaccess(
            wydawnictwo_ciagle,
            pbn_json,
            klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
        )

        assert wydawnictwo_ciagle.openaccess_licencja.skrot == "TST-LIC"
        assert wydawnictwo_ciagle.openaccess_tryb_dostepu is None
        assert wydawnictwo_ciagle.openaccess_czas_publikacji is None
        assert wydawnictwo_ciagle.openaccess_wersja_tekstu is None
        assert pbn_json == {}

    def test_pusty_blok_nie_wywala_importu(self, wydawnictwo_ciagle):
        pbn_json = {"openAccess": {}}

        importuj_openaccess(
            wydawnictwo_ciagle,
            pbn_json,
            klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
        )

        assert wydawnictwo_ciagle.openaccess_licencja is None
        assert wydawnictwo_ciagle.openaccess_tryb_dostepu is None
        assert pbn_json == {}

    def test_brak_openaccess_to_noop(self, wydawnictwo_ciagle):
        pbn_json = {"inne": "dane"}

        importuj_openaccess(
            wydawnictwo_ciagle,
            pbn_json,
            klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
        )

        assert wydawnictwo_ciagle.openaccess_licencja is None
        assert pbn_json == {"inne": "dane"}

    def test_release_date_iso_z_miesiacami(self, wydawnictwo_ciagle):
        pbn_json = {
            "openAccess": {"releaseDate": "2021-05-10T00:00:00", "months": 6}
        }

        importuj_openaccess(
            wydawnictwo_ciagle,
            pbn_json,
            klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
        )

        assert wydawnictwo_ciagle.openaccess_data_opublikowania == date(2021, 5, 10)
        assert wydawnictwo_ciagle.openaccess_ilosc_miesiecy == 6
        assert pbn_json == {}

    def test_release_date_rok_i_miesiac(self, wydawnictwo_ciagle):
        pbn_json = {
            "openAccess": {"releaseDateYear": "2020", "releaseDateMonth": "MARCH"}
        }

        importuj_openaccess(
            wydawnictwo_ciagle,
            pbn_json,
            klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
        )

        assert wydawnictwo_ciagle.openaccess_data_opublikowania == date(2020, 3, 1)
        assert pbn_json == {}

    def test_brak_licencji_w_slowniku_zglasza_blad(self, wydawnictwo_ciagle):
        # license obecne, ale nieznane w BPP — to realna luka konfiguracji,
        # nie cichy no-op (zachowanie sprzed fixa).
        pbn_json = {"openAccess": {"license": "NIEISTNIEJACA"}}

        with pytest.raises(ValueError):
            importuj_openaccess(
                wydawnictwo_ciagle,
                pbn_json,
                klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle,
            )


class TestUstawJezykOryginalny:
    def test_mapuje_kod_na_jezyk_orig(self, wydawnictwo_ciagle):
        # synthetyczny kod, którego nie ma w baseline
        baker.make("pbn_api.Language", code="qaa")
        jezyk = baker.make("bpp.Jezyk", pbn_uid_id="qaa")

        pbn_json = {"originalLanguage": "qaa"}
        ustaw_jezyk_oryginalny(wydawnictwo_ciagle, pbn_json)

        assert wydawnictwo_ciagle.jezyk_orig_id == jezyk.pk
        assert pbn_json == {}

    def test_nieznany_kod_zostawia_none(self, wydawnictwo_ciagle):
        # język oryginalny jest dla tłumaczeń i nullable — brak dopasowania to
        # None, a NIE język domyślny (inaczej niż mainLanguage → jezyk).
        pbn_json = {"originalLanguage": "qzz"}
        ustaw_jezyk_oryginalny(wydawnictwo_ciagle, pbn_json)

        assert wydawnictwo_ciagle.jezyk_orig is None
        assert pbn_json == {}

    def test_brak_klucza_to_noop(self, wydawnictwo_ciagle):
        pbn_json = {"inne": "dane"}
        ustaw_jezyk_oryginalny(wydawnictwo_ciagle, pbn_json)

        assert wydawnictwo_ciagle.jezyk_orig is None
        assert pbn_json == {"inne": "dane"}
