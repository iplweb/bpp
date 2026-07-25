"""Testy selektorów raportu kompletności danych POL-on.

Selektory odpowiadają za trzy rzeczy i każda z nich ma tu własny blok testów:

1. **zawężenie** — do okna ewaluacji, do przypiętych powiązań i do uczelni
   oglądającego (multi-tenant);
2. **klasyfikację** — rozróżnienie monografii od rozdziału po
   ``charakter_formalny.charakter_sloty``, wraz z osobną kategorią
   „nierozpoznany typ osiągnięcia” dla rekordów, których zaklasyfikować
   się nie da;
3. **anotację** — dołożenie po jednym polu logicznym na regułę oraz
   liczników braków wymaganych i warunkowych.

Budowniczych obiektów „kompletnych” (takich, których nie łapie ŻADNA reguła)
importujemy z :mod:`kompletnosc_polon.tests.test_reguly`. Zduplikowanie ich
tutaj oznaczałoby, że przy zmianie reguły trzeba pamiętać o dwóch miejscach —
a to gwarancja cichego rozjazdu.
"""

import datetime

import pytest
from model_bakery import baker

from bpp.const import CHARAKTER_SLOTY_KSIAZKA, CHARAKTER_SLOTY_ROZDZIAL
from ewaluacja_common.const import OKNO_EWALUACJI
from kompletnosc_polon import selektory
from kompletnosc_polon.const import OA_CZAS_PO_OPUBLIKOWANIU, Osiagniecie, Waga
from kompletnosc_polon.reguly import reguly_dla

from .test_reguly import (
    ROK,
    _kolejny_orcid,
    _kompletne_zwarte,
    _kompletny_artykul,
    _kompletny_patent,
)

PIERWSZY_ROK, OSTATNI_ROK = OKNO_EWALUACJI


# --------------------------------------------------------------------------
# Pomocnicy budujący ziarno raportu: powiązanie (autor, dyscyplina, rekord)
# --------------------------------------------------------------------------


def _jednostka(uczelnia=None):
    """Jednostka w podanej uczelni; przy braku uczelni — w nowej."""
    if uczelnia is None:
        uczelnia = baker.make("bpp.Uczelnia")
    return baker.make("bpp.Jednostka", uczelnia=uczelnia)


def _powiazanie(
    rekord,
    model_powiazania,
    *,
    uczelnia=None,
    jednostka=None,
    z_dyscyplina=True,
    przypieta=True,
    orcid=True,
    **nadpisz,
):
    """Zbuduj powiązanie autora z rekordem — jeden wiersz raportu.

    Powiązanie autor–dyscyplina na rok rekordu jest wymuszone przez
    ``BazaModeluOdpowiedzialnosciAutorow.clean()``, wołane z ``save()``,
    więc tworzymy je zawsze, gdy dyscyplina ma być ustawiona.
    """
    autor = baker.make("bpp.Autor", orcid=_kolejny_orcid() if orcid else None)

    dyscyplina = None
    if z_dyscyplina:
        dyscyplina = baker.make("bpp.Dyscyplina_Naukowa")
        baker.make(
            "bpp.Autor_Dyscyplina",
            autor=autor,
            rok=rekord.rok,
            dyscyplina_naukowa=dyscyplina,
            subdyscyplina_naukowa=None,
        )

    return baker.make(
        model_powiazania,
        rekord=rekord,
        autor=autor,
        jednostka=jednostka if jednostka is not None else _jednostka(uczelnia),
        dyscyplina_naukowa=dyscyplina,
        przypieta=przypieta,
        upowaznienie_pbn=True,
        oswiadczenie_ken=None,
        **nadpisz,
    )


def _artykul_z_autorem(rok=ROK, **kwargs):
    rekord = _kompletny_artykul()
    if rok != rekord.rok:
        rekord.rok = rok
        rekord.save()
    return _powiazanie(rekord, "bpp.Wydawnictwo_Ciagle_Autor", **kwargs)


def _charakter(charakter_sloty):
    """Charakter formalny o zadanym „charakterze dla slotów”.

    ``skrot`` bierzemy losowy (baker), bo słownik charakterów jest częścią
    baseline'u bazy i kolizja unikalności psułaby test.
    """
    return baker.make("bpp.Charakter_Formalny", charakter_sloty=charakter_sloty)


def _zwarte_z_autorem(charakter_sloty, rok=ROK, **kwargs):
    rekord = _kompletne_zwarte()
    rekord.rok = rok
    rekord.charakter_formalny = _charakter(charakter_sloty)
    rekord.save()
    return _powiazanie(rekord, "bpp.Wydawnictwo_Zwarte_Autor", **kwargs)


def _patent_z_autorem(rok=ROK, **kwargs):
    rekord = _kompletny_patent()
    if rok != rekord.rok:
        rekord.rok = rok
        rekord.save()
    return _powiazanie(rekord, "bpp.Patent_Autor", **kwargs)


def _pk(qs):
    return set(qs.values_list("pk", flat=True))


# --------------------------------------------------------------------------
# Zawężenie: okno ewaluacji
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_selektor_bierze_wylacznie_lata_z_okna():
    przed = _artykul_z_autorem(rok=PIERWSZY_ROK - 1)
    pierwszy = _artykul_z_autorem(rok=PIERWSZY_ROK)
    ostatni = _artykul_z_autorem(rok=OSTATNI_ROK)
    po = _artykul_z_autorem(rok=OSTATNI_ROK + 1)

    znalezione = _pk(selektory.powiazania(Osiagniecie.ARTYKUL))

    assert znalezione == {pierwszy.pk, ostatni.pk}, (
        "Obie granice okna muszą wchodzić do raportu, a lata spoza okna — nie"
    )
    assert przed.pk not in znalezione
    assert po.pk not in znalezione


@pytest.mark.django_db
def test_okno_da_sie_nadpisac_argumentem():
    stary = _artykul_z_autorem(rok=PIERWSZY_ROK - 1)
    nowy = _artykul_z_autorem(rok=PIERWSZY_ROK)

    znalezione = _pk(
        selektory.powiazania(Osiagniecie.ARTYKUL, okno=(PIERWSZY_ROK - 1, PIERWSZY_ROK))
    )

    assert znalezione == {stary.pk, nowy.pk}


# --------------------------------------------------------------------------
# Zawężenie: przypięta dyscyplina
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_odpieta_dyscyplina_nie_trafia_do_raportu():
    przypieta = _artykul_z_autorem()
    odpieta = _artykul_z_autorem(przypieta=False)

    znalezione = _pk(selektory.powiazania(Osiagniecie.ARTYKUL))

    assert znalezione == {przypieta.pk}
    assert odpieta.pk not in znalezione


@pytest.mark.django_db
def test_brak_dyscypliny_trafia_do_raportu_i_jest_zglaszany_jako_brak():
    """Powiązanie przypięte, ale bez dyscypliny, MUSI zostać w raporcie.

    Gdyby selektor odsiewał także ``dyscyplina_naukowa IS NULL``, reguły
    ``*_DYSCYPLINA`` nigdy nie mogłyby się uruchomić — a to one są jedynym
    sposobem, żeby użytkownik dowiedział się o braku dyscypliny.
    """
    bez_dyscypliny = _artykul_z_autorem(z_dyscyplina=False)

    qs = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    )
    wiersz = qs.get(pk=bez_dyscypliny.pk)

    assert getattr(wiersz, selektory.pole_reguly("ART_DYSCYPLINA")) is True


# --------------------------------------------------------------------------
# Zawężenie: uczelnia (multi-tenant)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_powiazanie_autora_z_innej_uczelni_nie_trafia():
    nasza = baker.make("bpp.Uczelnia")
    obca = baker.make("bpp.Uczelnia")

    nasze = _artykul_z_autorem(uczelnia=nasza)
    obce = _artykul_z_autorem(uczelnia=obca)

    znalezione = _pk(selektory.powiazania(Osiagniecie.ARTYKUL, uczelnia=nasza))

    assert znalezione == {nasze.pk}
    assert obce.pk not in znalezione


@pytest.mark.django_db
def test_bez_podanej_uczelni_selektor_nie_zawezia():
    pierwsze = _artykul_z_autorem(uczelnia=baker.make("bpp.Uczelnia"))
    drugie = _artykul_z_autorem(uczelnia=baker.make("bpp.Uczelnia"))

    znalezione = _pk(selektory.powiazania(Osiagniecie.ARTYKUL, uczelnia=None))

    assert znalezione == {pierwsze.pk, drugie.pk}


# --------------------------------------------------------------------------
# Ziarno raportu: (autor, dyscyplina, rekord)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_dwoch_wspolautorow_w_dwoch_dyscyplinach_daje_dwa_wiersze():
    """Jedna publikacja dwóch współautorów to DWA wpisy w wykazie pracowników.

    Brak (tu: ORCID) musi być przypisany tej osobie, której dotyczy — a nie
    „publikacji”.
    """
    rekord = _kompletny_artykul()
    jednostka = _jednostka()

    z_orcidem = _powiazanie(
        rekord, "bpp.Wydawnictwo_Ciagle_Autor", jednostka=jednostka, orcid=True
    )
    bez_orcidu = _powiazanie(
        rekord,
        "bpp.Wydawnictwo_Ciagle_Autor",
        jednostka=jednostka,
        orcid=False,
        kolejnosc=1,
    )

    assert z_orcidem.dyscyplina_naukowa_id != bez_orcidu.dyscyplina_naukowa_id, (
        "Test ma sens tylko przy dwóch RÓŻNYCH dyscyplinach"
    )

    qs = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    )
    assert _pk(qs) == {z_orcidem.pk, bez_orcidu.pk}

    pole = selektory.pole_reguly("ART_ORCID")
    assert getattr(qs.get(pk=bez_orcidu.pk), pole) is True
    assert getattr(qs.get(pk=z_orcidem.pk), pole) is False


# --------------------------------------------------------------------------
# Klasyfikacja: monografia vs rozdział vs „nierozpoznany typ”
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_monografia_i_rozdzial_rozroznia_charakter_slotow():
    monografia = _zwarte_z_autorem(CHARAKTER_SLOTY_KSIAZKA)
    rozdzial = _zwarte_z_autorem(CHARAKTER_SLOTY_ROZDZIAL)

    assert _pk(selektory.powiazania(Osiagniecie.MONOGRAFIA)) == {monografia.pk}
    assert _pk(selektory.powiazania(Osiagniecie.ROZDZIAL)) == {rozdzial.pk}


@pytest.mark.django_db
def test_rekord_bez_charakteru_slotow_nie_znika_tylko_trafia_do_nierozpoznanych():
    """Fixture instalacyjny zostawia ``charakter_sloty`` puste.

    Taki rekord nie daje się zaklasyfikować ani jako monografia, ani jako
    rozdział — ale nie wolno mu zniknąć po cichu, bo użytkownik uznałby, że
    raport go sprawdził.
    """
    nierozpoznany = _zwarte_z_autorem(None)
    monografia = _zwarte_z_autorem(CHARAKTER_SLOTY_KSIAZKA)

    assert nierozpoznany.pk not in _pk(selektory.powiazania(Osiagniecie.MONOGRAFIA))
    assert nierozpoznany.pk not in _pk(selektory.powiazania(Osiagniecie.ROZDZIAL))

    nierozpoznane = _pk(selektory.powiazania_nierozpoznane())
    assert nierozpoznane == {nierozpoznany.pk}
    assert monografia.pk not in nierozpoznane


@pytest.mark.django_db
def test_nierozpoznane_respektuja_okno_i_uczelnie():
    nasza = baker.make("bpp.Uczelnia")
    obca = baker.make("bpp.Uczelnia")

    nasz = _zwarte_z_autorem(None, uczelnia=nasza)
    _zwarte_z_autorem(None, uczelnia=obca)
    _zwarte_z_autorem(None, uczelnia=nasza, rok=PIERWSZY_ROK - 1)

    assert _pk(selektory.powiazania_nierozpoznane(uczelnia=nasza)) == {nasz.pk}


@pytest.mark.django_db
def test_patenty_i_artykuly_nie_podlegaja_klasyfikacji_po_charakterze():
    """Patent nie ma pola ``charakter_formalny``; artykuł zawsze jest pkt 4."""
    patent = _patent_z_autorem()
    artykul = _artykul_z_autorem()

    assert _pk(selektory.powiazania(Osiagniecie.PATENT)) == {patent.pk}
    assert _pk(selektory.powiazania(Osiagniecie.ARTYKUL)) == {artykul.pk}


# --------------------------------------------------------------------------
# Anotacja regułami
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_anotacja_doklada_pole_logiczne_dla_kazdej_reguly():
    _artykul_z_autorem()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    for regula in reguly_dla(Osiagniecie.ARTYKUL):
        pole = selektory.pole_reguly(regula.kod)
        assert hasattr(wiersz, pole), f"Brak anotacji {pole}"
        assert isinstance(getattr(wiersz, pole), bool)


@pytest.mark.django_db
@pytest.mark.parametrize("osiagniecie", list(Osiagniecie), ids=lambda o: o.value)
def test_anotacja_dziala_dla_kazdego_typu_i_nie_zwielokrotnia_wierszy(osiagniecie):
    """Anotacja nie może rozmnożyć ziarna przez JOIN-y warunków reguł.

    Wszystkie ścieżki w regułach idą przez relacje „do jednego” (FK w przód),
    więc jedno powiązanie musi dać dokładnie jeden wiersz — także wtedy, gdy
    dołożymy kilkanaście warunków naraz.
    """
    budowniczy = {
        Osiagniecie.ARTYKUL: lambda: _artykul_z_autorem(),
        Osiagniecie.MONOGRAFIA: lambda: _zwarte_z_autorem(CHARAKTER_SLOTY_KSIAZKA),
        Osiagniecie.ROZDZIAL: lambda: _zwarte_z_autorem(CHARAKTER_SLOTY_ROZDZIAL),
        Osiagniecie.PATENT: lambda: _patent_z_autorem(),
    }[osiagniecie]
    powiazanie = budowniczy()

    qs = selektory.z_regulami(selektory.powiazania(osiagniecie), osiagniecie)

    assert list(qs.values_list("pk", flat=True)) == [powiazanie.pk]
    assert selektory.naruszone_reguly(qs.get(), osiagniecie) == []


@pytest.mark.django_db
def test_rekord_kompletny_nie_ma_zadnego_braku():
    _artykul_z_autorem()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert selektory.naruszone_reguly(wiersz, Osiagniecie.ARTYKUL) == []
    assert getattr(wiersz, selektory.POLE_BRAKI_WYMAGANE) == 0
    assert getattr(wiersz, selektory.POLE_BRAKI_WARUNKOWE) == 0


@pytest.mark.django_db
def test_liczniki_zliczaja_braki_osobno_dla_kazdej_wagi():
    """Jeden brak wymagany (DOI) i jeden warunkowy (ORCID)."""
    powiazanie = _artykul_z_autorem(orcid=False)
    rekord = powiazanie.rekord
    rekord.doi = None
    rekord.www = ""
    rekord.public_www = ""
    rekord.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert getattr(wiersz, selektory.pole_reguly("ART_DOI")) is True
    assert getattr(wiersz, selektory.pole_reguly("ART_ORCID")) is True
    assert getattr(wiersz, selektory.POLE_BRAKI_WYMAGANE) == 1
    assert getattr(wiersz, selektory.POLE_BRAKI_WARUNKOWE) == 1

    naruszone = selektory.naruszone_reguly(wiersz, Osiagniecie.ARTYKUL)
    assert {regula.kod for regula in naruszone} == {"ART_DOI", "ART_ORCID"}


@pytest.mark.django_db
def test_liczniki_zgadzaja_sie_z_lista_naruszonych_regul():
    _artykul_z_autorem(orcid=False, z_dyscyplina=False)

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()
    naruszone = selektory.naruszone_reguly(wiersz, Osiagniecie.ARTYKUL)

    wymagane = [r for r in naruszone if r.waga == Waga.WYMAGANE]
    warunkowe = [r for r in naruszone if r.waga == Waga.WARUNKOWE]

    assert getattr(wiersz, selektory.POLE_BRAKI_WYMAGANE) == len(wymagane)
    assert getattr(wiersz, selektory.POLE_BRAKI_WARUNKOWE) == len(warunkowe)
    assert wymagane and warunkowe, "Test ma sens tylko przy brakach obu wag"


@pytest.mark.django_db
def test_naruszone_reguly_zwraca_obiekty_regul_z_opisem_i_paragrafem():
    powiazanie = _artykul_z_autorem()
    powiazanie.upowaznienie_pbn = False
    powiazanie.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()
    (regula,) = selektory.naruszone_reguly(wiersz, Osiagniecie.ARTYKUL)

    assert regula.kod == "ART_UPOWAZNIENIE"
    assert regula.paragraf == "§ 2 ust. 10 pkt 4 lit. d"
    assert regula.opis


@pytest.mark.django_db
def test_naruszone_reguly_wymagaja_zanotowanego_wiersza():
    _artykul_z_autorem()
    wiersz = selektory.powiazania(Osiagniecie.ARTYKUL).get()

    with pytest.raises(ValueError):
        selektory.naruszone_reguly(wiersz, Osiagniecie.ARTYKUL)


@pytest.mark.django_db
def test_anotacja_rozdzialu_uzywa_wylacznie_regul_rozdzialu():
    _zwarte_z_autorem(CHARAKTER_SLOTY_ROZDZIAL)

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ROZDZIAL), Osiagniecie.ROZDZIAL
    ).get()

    assert hasattr(wiersz, selektory.pole_reguly("ROZ_NADRZEDNE"))
    assert not hasattr(wiersz, selektory.pole_reguly("MON_ISBN"))


def test_pole_reguly_wyprowadza_nazwe_z_kodu():
    assert selektory.pole_reguly("ART_DOI") == "brak_ART_DOI"


# --------------------------------------------------------------------------
# Warunkowość Open Access
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_praca_bez_trybu_open_access_nie_generuje_brakow_oa():
    _artykul_z_autorem()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    for kod in (
        "ART_OA_WERSJA",
        "ART_OA_LICENCJA",
        "ART_OA_DATA",
        "ART_OA_CZAS",
        "ART_OA_MIESIACE",
    ):
        assert getattr(wiersz, selektory.pole_reguly(kod)) is False, (
            f"Reguła {kod} zadziałała mimo braku oznaczenia Open Access"
        )


@pytest.mark.django_db
def test_udostepnienie_inne_niz_po_opublikowaniu_nie_wymaga_liczby_miesiecy():
    from bpp.models import Czas_Udostepnienia_OpenAccess

    czas, _ = Czas_Udostepnienia_OpenAccess.objects.get_or_create(
        skrot="BEFORE_PUBLICATION",
        defaults={"nazwa": "przed opublikowaniem"},
    )
    assert czas.skrot != OA_CZAS_PO_OPUBLIKOWANIU

    powiazanie = _artykul_z_autorem()
    rekord = powiazanie.rekord
    rekord.openaccess_tryb_dostepu = baker.make(
        "bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle"
    )
    rekord.openaccess_wersja_tekstu = baker.make("bpp.Wersja_Tekstu_OpenAccess")
    rekord.openaccess_licencja = baker.make("bpp.Licencja_OpenAccess")
    rekord.openaccess_data_opublikowania = datetime.date(ROK, 3, 1)
    rekord.openaccess_czas_publikacji = czas
    rekord.openaccess_ilosc_miesiecy = None
    rekord.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert getattr(wiersz, selektory.pole_reguly("ART_OA_MIESIACE")) is False
    assert selektory.naruszone_reguly(wiersz, Osiagniecie.ARTYKUL) == []
