"""Dyscypliny nowych rekordów z oświadczeń instytucji w PBN (FD#477).

Reguła ścisła: przypisujemy tylko wtedy, gdy osoba, rola, dyscyplina
i przypisanie dyscypliny autorowi na dany rok zgadzają się bez zgadywania.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa, Wydawnictwo_Zwarte
from pbn_api.models import OswiadczenieInstytucji
from pbn_uzgadnianie import silnik
from pbn_uzgadnianie.silnik import uzgodnij

pytestmark = pytest.mark.django_db

MEDYCYNA = "nauki medyczne"


@pytest.fixture
def medycyna(db):
    return baker.make(Dyscyplina_Naukowa, nazwa=MEDYCYNA, kod="3.2")


@pytest.fixture
def praca(klient, ksiazka_pbn):
    """Praca na profilu z jednym autorem → ``(pbn_uid, PBN UID osoby)``."""
    obiekt = ksiazka_pbn("Monografia z oświadczeniem o dyscyplinie")
    klient.dodaj("pbn-osw", obiekt)
    return "pbn-osw", next(iter(obiekt["authors"]))


def _autor(osoba):
    return Autor.objects.get(pbn_uid_id=osoba)


def _wiersz():
    return Wydawnictwo_Zwarte.objects.get(pbn_uid_id="pbn-osw").autorzy_set.get()


def test_nowy_rekord_dostaje_dyscypline_z_oswiadczenia(
    klient, praca, przebieg, medycyna
):
    pbn_uid, osoba = praca
    baker.make(
        Autor_Dyscyplina, autor=_autor(osoba), rok=2026, dyscyplina_naukowa=medycyna
    )
    klient.oswiadcz(pbn_uid, osoba, MEDYCYNA)

    wynik = uzgodnij(przebieg(), klient)

    wiersz = _wiersz()
    assert wiersz.dyscyplina_naukowa == medycyna
    assert wiersz.profil_orcid is True
    assert str(wiersz.data_oswiadczenia) == "2026-03-02"
    assert wynik.wynik[0]["dyscypliny"] == [
        {
            "osoba": str(wiersz.autor),
            "dyscyplina": MEDYCYNA,
            "przypisano": True,
            "powod": "",
        }
    ]
    # Oświadczenie trafiło też do lokalnej kopii (dla komparatorów).
    assert OswiadczenieInstytucji.objects.filter(publicationId_id=pbn_uid).exists()


def test_autor_bez_oswiadczenia_zostaje_bez_dyscypliny_i_jest_w_raporcie(
    klient, praca, przebieg, medycyna
):
    _pbn_uid, osoba = praca
    baker.make(
        Autor_Dyscyplina, autor=_autor(osoba), rok=2026, dyscyplina_naukowa=medycyna
    )

    wynik = uzgodnij(przebieg(), klient)

    assert _wiersz().dyscyplina_naukowa is None
    (wpis,) = wynik.wynik[0]["dyscypliny"]
    assert wpis["przypisano"] is False
    assert "Brak oświadczenia" in wpis["powod"]


def test_autor_bez_dyscypliny_na_ten_rok_nie_jest_zgadywany(
    klient, praca, przebieg, medycyna
):
    """Dotychczasowy import oświadczeń sam dopisałby autorowi dyscyplinę na
    ten rok. Uzgadnianie tego nie robi — zostawia do decyzji redaktora."""
    pbn_uid, osoba = praca
    baker.make(
        Autor_Dyscyplina, autor=_autor(osoba), rok=2025, dyscyplina_naukowa=medycyna
    )
    klient.oswiadcz(pbn_uid, osoba, MEDYCYNA)

    wynik = uzgodnij(przebieg(), klient)

    assert _wiersz().dyscyplina_naukowa is None
    assert not Autor_Dyscyplina.objects.filter(rok=2026).exists()
    (wpis,) = wynik.wynik[0]["dyscypliny"]
    assert wpis["przypisano"] is False
    assert "na rok 2026" in wpis["powod"]


def test_nieznana_dyscyplina_nie_jest_przypisywana(klient, praca, przebieg):
    pbn_uid, osoba = praca
    klient.oswiadcz(pbn_uid, osoba, "dyscyplina, której nie ma w słowniku")

    wynik = uzgodnij(przebieg(), klient)

    assert _wiersz().dyscyplina_naukowa is None
    assert "nie ma w słowniku" in wynik.wynik[0]["dyscypliny"][0]["powod"]


def test_oswiadczenie_osoby_spoza_rekordu_jest_w_raporcie(
    klient, praca, przebieg, autor_pbn
):
    pbn_uid, osoba = praca
    klient.oswiadcz(pbn_uid, autor_pbn("Postronny"), MEDYCYNA)

    wynik = uzgodnij(przebieg(), klient)

    powody = [d["powod"] for d in wynik.wynik[0]["dyscypliny"]]
    assert any("której nie ma wśród" in p for p in powody)
    assert _wiersz().dyscyplina_naukowa is None


def test_oswiadczenie_wycofane_w_pbn_a_obecne_w_kopii_nie_jest_stosowane(
    klient, praca, przebieg, medycyna
):
    """Lokalna kopia nie zapomina oświadczeń usuniętych w PBN — decyduje
    to, co PBN zwrócił w tym przebiegu."""
    pbn_uid, osoba = praca
    baker.make(
        Autor_Dyscyplina, autor=_autor(osoba), rok=2026, dyscyplina_naukowa=medycyna
    )
    klient.oswiadcz(pbn_uid, osoba, MEDYCYNA)
    uzgodnij(przebieg(tryb="podglad"), klient)  # kopia ma już oświadczenie…
    klient.oswiadczenia.clear()  # …a w PBN je wycofano
    klient.oswiadcz(pbn_uid, osoba, None)
    klient.oswiadczenia.clear()

    uzgodnij(przebieg(), klient)

    assert _wiersz().dyscyplina_naukowa is None


def test_podglad_dyscyplin_rowny_wykonaniu_i_nic_nie_zostawia(
    klient, praca, przebieg, medycyna
):
    pbn_uid, osoba = praca
    baker.make(
        Autor_Dyscyplina, autor=_autor(osoba), rok=2026, dyscyplina_naukowa=medycyna
    )
    klient.oswiadcz(pbn_uid, osoba, MEDYCYNA)

    podglad = uzgodnij(przebieg(tryb="podglad"), klient)

    assert not Wydawnictwo_Zwarte.objects.exists()
    assert podglad.wynik[0]["dyscypliny"][0]["przypisano"] is True
    klient.wywolania.clear()

    wykonanie = uzgodnij(przebieg(na_podstawie=podglad), klient)

    assert klient.wywolania == []
    assert wykonanie.wynik[0]["dyscypliny"] == podglad.wynik[0]["dyscypliny"]
    assert _wiersz().dyscyplina_naukowa == medycyna


def test_dyscypliny_w_istniejacym_rekordzie_nie_sa_zmieniane_tylko_raport(
    klient, praca, przebieg, medycyna
):
    pbn_uid, osoba = praca
    uzgodnij(przebieg(), klient)  # rekord powstaje bez dyscypliny
    baker.make(
        Autor_Dyscyplina, autor=_autor(osoba), rok=2026, dyscyplina_naukowa=medycyna
    )
    klient.oswiadcz(pbn_uid, osoba, MEDYCYNA)  # oświadczenie pojawia się później

    wynik = uzgodnij(przebieg(), klient)

    assert _wiersz().dyscyplina_naukowa is None, "zmieniono istniejący rekord"
    wpis = wynik.wynik[0]
    assert wpis["kategoria"] == silnik.ROZNI_SIE
    (roznica,) = wpis["roznice"]
    assert (roznica["pole"], roznica["bpp"], roznica["pbn"]) == (
        f"Dyscyplina ({_autor(osoba)})",
        "",
        MEDYCYNA,
    )
    # Pusta strona jest w raporcie opisana słowami, nie pustą komórką.
    from pbn_uzgadnianie.raport import wiersze_roznic

    assert wiersze_roznic(wpis)[0]["bpp"] == "brak dyscypliny w rekordzie BPP"


def test_brak_oswiadczenia_w_pbn_jest_nazwany_slowami(
    klient, praca, przebieg, medycyna
):
    from pbn_uzgadnianie.raport import wiersze_roznic

    _pbn_uid, osoba = praca
    uzgodnij(przebieg(), klient)
    baker.make(
        Autor_Dyscyplina, autor=_autor(osoba), rok=2026, dyscyplina_naukowa=medycyna
    )
    wiersz = _wiersz()
    wiersz.dyscyplina_naukowa = medycyna
    wiersz.save()

    wynik = uzgodnij(przebieg(), klient)

    (wiersz_raportu,) = wiersze_roznic(wynik.wynik[0])
    assert wiersz_raportu["bpp"] == MEDYCYNA
    assert wiersz_raportu["pbn"] == "brak oświadczenia w PBN"
    assert "brak oświadczenia w PBN" in str(wiersz_raportu["pbn_html"])
