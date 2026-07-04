"""Testy obsługi za długich słów kluczowych i tytułów w wielu językach.

- ``przetworz_slowa_kluczowe`` — tagi dłuższe niż ``MAKSYMALNA_DLUGOSC_TAGU``
  (taggit ``Tag.name``/``Tag.slug`` to varchar(100)) nie wywalają importu, tylko
  są pomijane, logowane i zapisywane do ``adnotacje`` pod ``tagsTooLong``.
- ``przetworz_tytuly`` — tytuł angielski (lub polski) ląduje w ``tytul``, a tytuły
  w pozostałych językach trafiają do osobnych wierszy ``Wydawnictwo_*_Tytul``
  (analogicznie do streszczeń), z dowiązaniem do słownika ``Jezyk`` jeśli się da.
"""

import pytest
from django.db import IntegrityError
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle_Tytul
from pbn_integrator.importer import (
    przetworz_slowa_kluczowe,
    przetworz_tytuly,
)
from pbn_integrator.importer.helpers import MAKSYMALNA_DLUGOSC_TAGU


@pytest.fixture
def wydawnictwo_ciagle(db):
    # adnotacje/tytul puste — baker domyślnie wstawiłby losowy tekst
    return baker.make("bpp.Wydawnictwo_Ciagle", adnotacje="", tytul="")


class TestPrzetworzSlowaKluczowe:
    def test_dodaje_poprawne_tagi(self, wydawnictwo_ciagle):
        przetworz_slowa_kluczowe({"alfa", "beta"}, None, wydawnictwo_ciagle)

        assert set(wydawnictwo_ciagle.slowa_kluczowe.names()) == {"alfa", "beta"}
        assert "tagsTooLong" not in wydawnictwo_ciagle.adnotacje

    def test_za_dlugi_tag_pomijany_i_w_adnotacjach(self, wydawnictwo_ciagle):
        za_dlugi = "x" * (MAKSYMALNA_DLUGOSC_TAGU + 50)

        przetworz_slowa_kluczowe({za_dlugi, "ok"}, None, wydawnictwo_ciagle)

        assert set(wydawnictwo_ciagle.slowa_kluczowe.names()) == {"ok"}
        wydawnictwo_ciagle.refresh_from_db()
        assert "tagsTooLong" in wydawnictwo_ciagle.adnotacje
        assert za_dlugi in wydawnictwo_ciagle.adnotacje

    def test_sam_za_dlugi_nie_wywala_importu(self, wydawnictwo_ciagle):
        za_dlugi = "y" * (MAKSYMALNA_DLUGOSC_TAGU + 1)

        przetworz_slowa_kluczowe({za_dlugi}, None, wydawnictwo_ciagle)

        assert list(wydawnictwo_ciagle.slowa_kluczowe.names()) == []
        wydawnictwo_ciagle.refresh_from_db()
        assert "tagsTooLong" in wydawnictwo_ciagle.adnotacje

    def test_tag_na_granicy_limitu_dodawany(self, wydawnictwo_ciagle):
        na_granicy = "z" * MAKSYMALNA_DLUGOSC_TAGU

        przetworz_slowa_kluczowe({na_granicy}, None, wydawnictwo_ciagle)

        assert list(wydawnictwo_ciagle.slowa_kluczowe.names()) == [na_granicy]
        assert "tagsTooLong" not in wydawnictwo_ciagle.adnotacje


class TestPrzetworzTytuly:
    def _tytuly(self, rekord):
        return {t.kod_jezyka_pbn: t for t in rekord.dodatkowe_tytuly.all()}

    def test_preferuje_angielski_reszta_jako_wiersze(self, wydawnictwo_ciagle):
        pbn_json = {"titles": {"eng": "English title", "pol": "Polski tytuł"}}

        przetworz_tytuly(pbn_json, wydawnictwo_ciagle, Wydawnictwo_Ciagle_Tytul)

        wydawnictwo_ciagle.refresh_from_db()
        assert wydawnictwo_ciagle.tytul == "English title"
        tytuly = self._tytuly(wydawnictwo_ciagle)
        assert set(tytuly) == {"pol"}
        assert tytuly["pol"].tytul == "Polski tytuł"
        assert pbn_json == {}

    def test_polski_gdy_brak_angielskiego(self, wydawnictwo_ciagle):
        pbn_json = {"titles": {"pol": "Polski tytuł"}}

        przetworz_tytuly(pbn_json, wydawnictwo_ciagle, Wydawnictwo_Ciagle_Tytul)

        wydawnictwo_ciagle.refresh_from_db()
        assert wydawnictwo_ciagle.tytul == "Polski tytuł"
        assert wydawnictwo_ciagle.dodatkowe_tytuly.count() == 0
        assert pbn_json == {}

    def test_obce_jezyki_jako_wiersze(self, wydawnictwo_ciagle):
        pbn_json = {
            "titles": {
                "eng": "English",
                "deu": "Deutscher Titel",
                "rus": "Русское название",
            }
        }

        przetworz_tytuly(pbn_json, wydawnictwo_ciagle, Wydawnictwo_Ciagle_Tytul)

        wydawnictwo_ciagle.refresh_from_db()
        assert wydawnictwo_ciagle.tytul == "English"
        tytuly = self._tytuly(wydawnictwo_ciagle)
        assert set(tytuly) == {"deu", "rus"}
        assert tytuly["deu"].tytul == "Deutscher Titel"
        assert tytuly["rus"].tytul == "Русское название"
        assert pbn_json == {}

    def test_brak_eng_i_pol_nie_wywala_importu(self, wydawnictwo_ciagle):
        # wcześniej: KeyError 'pol' / 'eng'
        pbn_json = {"titles": {"deu": "Nur Deutsch", "lit": "Tik lietuviškai"}}

        przetworz_tytuly(pbn_json, wydawnictwo_ciagle, Wydawnictwo_Ciagle_Tytul)

        wydawnictwo_ciagle.refresh_from_db()
        assert wydawnictwo_ciagle.tytul == ""  # nic nie wybrano do tytul
        assert set(self._tytuly(wydawnictwo_ciagle)) == {"deu", "lit"}
        assert pbn_json == {}

    def test_dowiazuje_jezyk_ze_slownika(self, wydawnictwo_ciagle):
        # synthetyczny kod, którego nie ma w baseline
        baker.make("pbn_api.Language", code="qaa")
        jezyk = baker.make("bpp.Jezyk", pbn_uid_id="qaa")

        pbn_json = {"titles": {"eng": "English", "qaa": "Tytuł testowy"}}
        przetworz_tytuly(pbn_json, wydawnictwo_ciagle, Wydawnictwo_Ciagle_Tytul)

        wiersz = wydawnictwo_ciagle.dodatkowe_tytuly.get(kod_jezyka_pbn="qaa")
        assert wiersz.jezyk_id == jezyk.pk
        assert wiersz.tytul == "Tytuł testowy"

    def test_nieznany_jezyk_zostaje_bez_jezyka_ale_z_kodem(self, wydawnictwo_ciagle):
        pbn_json = {"titles": {"eng": "English", "qzz": "Bez słownika"}}

        przetworz_tytuly(pbn_json, wydawnictwo_ciagle, Wydawnictwo_Ciagle_Tytul)

        wiersz = wydawnictwo_ciagle.dodatkowe_tytuly.get(kod_jezyka_pbn="qzz")
        assert wiersz.jezyk_id is None
        assert wiersz.tytul == "Bez słownika"

    def test_brak_titles_to_noop(self, wydawnictwo_ciagle):
        pbn_json = {"inne": "dane"}

        przetworz_tytuly(pbn_json, wydawnictwo_ciagle, Wydawnictwo_Ciagle_Tytul)

        assert wydawnictwo_ciagle.tytul == ""
        assert wydawnictwo_ciagle.dodatkowe_tytuly.count() == 0
        assert pbn_json == {"inne": "dane"}

    def test_unikalnosc_jezyka_na_rekord(self, wydawnictwo_ciagle):
        Wydawnictwo_Ciagle_Tytul.objects.create(
            rekord=wydawnictwo_ciagle, kod_jezyka_pbn="deu", tytul="A"
        )
        with pytest.raises(IntegrityError):
            Wydawnictwo_Ciagle_Tytul.objects.create(
                rekord=wydawnictwo_ciagle, kod_jezyka_pbn="deu", tytul="B"
            )
