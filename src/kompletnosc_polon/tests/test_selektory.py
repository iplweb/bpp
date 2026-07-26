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
from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.const import (
    CHARAKTER_SLOTY_KSIAZKA,
    CHARAKTER_SLOTY_REFERAT,
    CHARAKTER_SLOTY_ROZDZIAL,
    RODZAJ_PBN_ARTYKUL,
    RODZAJ_PBN_KSIAZKA,
)
from ewaluacja_common.const import OKNO_EWALUACJI
from kompletnosc_polon import selektory
from kompletnosc_polon.const import OA_CZAS_PO_OPUBLIKOWANIU, Osiagniecie, Waga
from kompletnosc_polon.reguly import reguly_dla

from .test_reguly import (
    ROK,
    _kolejna_dyscyplina,
    _kolejny_orcid,
    _kompletne_zwarte,
    _kompletny_artykul,
    _kompletny_patent,
)

#: Pierwszy rok okna raportu. Górnej granicy świadomie tu NIE rozpakowujemy:
#: :data:`OKNO_EWALUACJI` ma ją dziś nieustaloną (``None``) i testy muszą
#: mówić o oknie otwartym i domkniętym osobno — patrz blok „Zawężenie: okno”.
PIERWSZY_ROK = OKNO_EWALUACJI[0]


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
        dyscyplina = _kolejna_dyscyplina()
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


def _artykul_z_autorem(rok=ROK, rodzaj_pbn=RODZAJ_PBN_ARTYKUL, **kwargs):
    """Powiązanie autora z artykułem; ``rodzaj_pbn`` zmienia typ rekordu.

    ``rodzaj_pbn=None`` odwzorowuje streszczenie zjazdowe, list do redakcji,
    recenzję albo komunikat — wydawnictwa ciągłe, które nie są artykułem
    naukowym z § 2 ust. 10 pkt 4 i nigdy nie jadą do PBN.
    """
    rekord = _kompletny_artykul()
    rekord.rok = rok
    if rodzaj_pbn != RODZAJ_PBN_ARTYKUL:
        rekord.charakter_formalny = baker.make(
            "bpp.Charakter_Formalny", rodzaj_pbn=rodzaj_pbn
        )
    rekord.save()
    return _powiazanie(rekord, "bpp.Wydawnictwo_Ciagle_Autor", **kwargs)


def _charakter(charakter_sloty, rodzaj_pbn=RODZAJ_PBN_KSIAZKA):
    """Charakter formalny o zadanym „charakterze dla slotów”.

    ``skrot`` bierzemy losowy (baker), bo słownik charakterów jest częścią
    baseline'u bazy i kolizja unikalności psułaby test.

    ``rodzaj_pbn`` domyślnie ustawiamy na niepusty, bo to on odpowiada na
    pytanie „czy ten rekord w ogóle jedzie do PBN”. Charakter bez tej wartości
    (np. TŁ, SKR, PZ, BR, IN) jest sklasyfikowany poprawnie i celowo poza
    zakresem raportu — do sekcji „nierozpoznane” trafiać NIE ma.
    """
    return baker.make(
        "bpp.Charakter_Formalny",
        charakter_sloty=charakter_sloty,
        rodzaj_pbn=rodzaj_pbn,
    )


def _zwarte_z_autorem(
    charakter_sloty, rok=ROK, rodzaj_pbn=RODZAJ_PBN_KSIAZKA, **kwargs
):
    rekord = _kompletne_zwarte()
    rekord.rok = rok
    rekord.charakter_formalny = _charakter(charakter_sloty, rodzaj_pbn)
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


def _identyfikator(powiazanie):
    """Para (model, pk) — jednoznaczna także przy mieszaniu dwóch modeli.

    Sekcja „nierozpoznane” łączy powiązania z wydawnictwami zwartymi
    i ciągłymi, a to dwie tabele o **niezależnych sekwencjach** kluczy
    głównych: samo ``pk`` potrafiłoby się powtórzyć i asercja na zbiorze
    byłaby fałszywie zielona.
    """
    return (powiazanie._meta.model_name, powiazanie.pk)


def _nierozpoznane(**kwargs):
    """Zbiór identyfikatorów wszystkich nierozpoznanych powiązań."""
    return {
        _identyfikator(powiazanie)
        for qs in selektory.powiazania_nierozpoznane(**kwargs)
        for powiazanie in qs
    }


# --------------------------------------------------------------------------
# Zawężenie: okno ewaluacji
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_selektor_odsiewa_lata_sprzed_okna():
    """Dolna granica okna gryzie i gryźć musi — to ona wchodzi do raportu.

    Rok wcześniejszy niż pierwszy rok okna należy do POPRZEDNIEJ ewaluacji;
    jego braki nie są już do uzupełnienia w tym sprawozdaniu.
    """
    przed = _artykul_z_autorem(rok=PIERWSZY_ROK - 1)
    pierwszy = _artykul_z_autorem(rok=PIERWSZY_ROK)

    znalezione = _pk(selektory.powiazania(Osiagniecie.ARTYKUL))

    assert znalezione == {pierwszy.pk}, (
        "Pierwszy rok okna wchodzi do raportu, rok sprzed okna — nie"
    )
    assert przed.pk not in znalezione


@pytest.mark.django_db
def test_otwarta_gorna_granica_bierze_takze_odlegly_rok():
    """Sens ``ostatni rok = None``: raport nie przestaje widzieć nowych lat.

    Rok 2035 jest tu umyślnie absurdalnie daleki — chodzi o wykazanie, że
    przy nieustalonej górnej granicy żadne odcięcie z góry nie działa.
    """
    daleki = _artykul_z_autorem(rok=2035)
    tuz_przed_oknem = _artykul_z_autorem(rok=PIERWSZY_ROK - 1)

    znalezione = _pk(
        selektory.powiazania(Osiagniecie.ARTYKUL, okno=(PIERWSZY_ROK, None))
    )

    assert znalezione == {daleki.pk}, (
        "Otwarte okno bierze rekord z dowolnie odległego roku, ale dolna "
        "granica nadal obowiązuje"
    )
    assert tuz_przed_oknem.pk not in znalezione


@pytest.mark.django_db
def test_domyslne_okno_bierze_rekord_z_odleglego_roku():
    """To samo, ale na STAŁEJ — bo to ona decyduje o zachowaniu raportu.

    Gdy MEiN ogłosi długość okresu ewaluacyjnego i granica zostanie
    domknięta, test przestanie mieć zastosowanie (rok „daleki” wypadnie
    z okna zgodnie z przepisem) — dlatego wtedy się pomija, a nie psuje.
    """
    pierwszy_rok, ostatni_rok = OKNO_EWALUACJI
    if ostatni_rok is not None:
        pytest.skip(
            "Górna granica okna została domknięta — otwartego okna nie ma "
            "już czego sprawdzać na stałej"
        )

    daleki = _artykul_z_autorem(rok=pierwszy_rok + 9)

    assert daleki.pk in _pk(selektory.powiazania(Osiagniecie.ARTYKUL))


@pytest.mark.django_db
def test_domkniete_okno_odcina_lata_po_gornej_granicy():
    """Po domknięciu granicy górne odcięcie ma znów działać.

    Okno podajemy jawnie argumentem, więc test opisuje przyszły stan
    (``OKNO_EWALUACJI = (2026, <rok>)``) bez ruszania stałej.
    """
    ostatni_rok = PIERWSZY_ROK + 1
    ostatni = _artykul_z_autorem(rok=ostatni_rok)
    po = _artykul_z_autorem(rok=ostatni_rok + 1)

    znalezione = _pk(
        selektory.powiazania(Osiagniecie.ARTYKUL, okno=(PIERWSZY_ROK, ostatni_rok))
    )

    assert znalezione == {ostatni.pk}, (
        "Ostatni rok domkniętego okna wchodzi do raportu, następny — nie"
    )
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

    nierozpoznane = _nierozpoznane()
    assert nierozpoznane == {_identyfikator(nierozpoznany)}
    assert _identyfikator(monografia) not in nierozpoznane


@pytest.mark.django_db
def test_charakter_spoza_pbn_nie_trafia_do_nierozpoznanych():
    """Sekcja „raport tego nie sprawdził” to zarzut, nie worek na wszystko.

    Migracje ``0173`` i ``0225`` ustawiają ``charakter_sloty`` wyłącznie dla
    KS/KSP/KSZ, ROZ/ROZS i PRZ/ZRZ, więc pusta wartość jest normą dla frg, TŁ,
    SKR, PZ, BR i IN. Te charaktery są sklasyfikowane poprawnie i celowo —
    po prostu nie jadą do PBN (``rodzaj_pbn`` puste). Zgłoszenie ich jako
    „niesprawdzonych” byłoby fałszywym alarmem.
    """
    spoza_pbn = _zwarte_z_autorem(None, rodzaj_pbn=None)
    nierozpoznany = _zwarte_z_autorem(None, rodzaj_pbn=RODZAJ_PBN_KSIAZKA)

    nierozpoznane = _nierozpoznane()

    assert nierozpoznane == {_identyfikator(nierozpoznany)}
    assert _identyfikator(spoza_pbn) not in nierozpoznane


@pytest.mark.django_db
def test_referat_nie_trafia_do_nierozpoznanych():
    """Referat jest zaklasyfikowany JAWNIE — to nie jest brak danych."""
    referat = _zwarte_z_autorem(CHARAKTER_SLOTY_REFERAT)

    assert _identyfikator(referat) not in _nierozpoznane()


@pytest.mark.django_db
def test_nierozpoznane_respektuja_okno_i_uczelnie():
    nasza = baker.make("bpp.Uczelnia")
    obca = baker.make("bpp.Uczelnia")

    nasz = _zwarte_z_autorem(None, uczelnia=nasza)
    _zwarte_z_autorem(None, uczelnia=obca)
    _zwarte_z_autorem(None, uczelnia=nasza, rok=PIERWSZY_ROK - 1)

    assert _nierozpoznane(uczelnia=nasza) == {_identyfikator(nasz)}


@pytest.mark.django_db
def test_ciagle_bez_rodzaju_pbn_nie_znika_tylko_trafia_do_nierozpoznanych():
    """Nieustawiony ``rodzaj_pbn`` NIE może wyciszyć wszystkich artykułów.

    ``Charakter_Formalny.rodzaj_pbn`` nie jest wypełniane przez fixture
    instalacyjny — administrator ustawia je per instalacja. Dopóki tego nie
    zrobi dla charakteru „AC”, każdy artykuł wypada z :func:`powiazania`;
    gdyby wypadał też z sekcji nierozpoznanych, użytkownik zobaczyłby raport
    bez ani jednego artykułu i uznałby, że artykuły są w porządku.
    """
    nierozpoznany = _artykul_z_autorem(rodzaj_pbn=None)

    assert nierozpoznany.pk not in _pk(selektory.powiazania(Osiagniecie.ARTYKUL))
    assert _nierozpoznane() == {_identyfikator(nierozpoznany)}


@pytest.mark.django_db
def test_artykul_z_ustawionym_rodzajem_pbn_nie_trafia_do_nierozpoznanych():
    """Rekord audytowany normalnie nie ma prawa być zarazem „niesprawdzony”."""
    artykul = _artykul_z_autorem()

    assert artykul.pk in _pk(selektory.powiazania(Osiagniecie.ARTYKUL))
    assert _identyfikator(artykul) not in _nierozpoznane()


@pytest.mark.django_db
def test_ciagle_o_jawnie_innym_rodzaju_pbn_nie_trafia_do_nierozpoznanych():
    """Ciągłe oznaczone jako książka jest sklasyfikowane — po prostu poza pkt 4.

    Tak samo jak referat wśród zwartych: raport go nie audytuje, ale to nie
    jest brak danych, więc „raport tego nie sprawdził” byłoby zarzutem
    postawionym poprawnie wypełnionemu rekordowi.
    """
    ksiazkowe = _artykul_z_autorem(rodzaj_pbn=RODZAJ_PBN_KSIAZKA)

    assert _identyfikator(ksiazkowe) not in _nierozpoznane()


@pytest.mark.django_db
def test_nierozpoznane_lacza_zwarte_i_ciagle_w_jeden_zbior():
    """Sekcja jest JEDNA — obsługuje oba modele naraz."""
    zwarte = _zwarte_z_autorem(None)
    ciagle = _artykul_z_autorem(rodzaj_pbn=None)

    assert _nierozpoznane() == {_identyfikator(zwarte), _identyfikator(ciagle)}


@pytest.mark.django_db
def test_nierozpoznane_ciagle_respektuja_okno_i_uczelnie():
    nasza = baker.make("bpp.Uczelnia")
    obca = baker.make("bpp.Uczelnia")

    nasz = _artykul_z_autorem(rodzaj_pbn=None, uczelnia=nasza)
    _artykul_z_autorem(rodzaj_pbn=None, uczelnia=obca)
    _artykul_z_autorem(rodzaj_pbn=None, uczelnia=nasza, rok=PIERWSZY_ROK - 1)

    assert _nierozpoznane(uczelnia=nasza) == {_identyfikator(nasz)}


@pytest.mark.django_db
def test_patent_nie_podlega_klasyfikacji_po_charakterze_formalnym():
    """Patent nie ma pola ``charakter_formalny`` w ogóle."""
    patent = _patent_z_autorem()

    assert _pk(selektory.powiazania(Osiagniecie.PATENT)) == {patent.pk}


@pytest.mark.django_db
def test_streszczenie_zjazdowe_nie_jest_audytowane_jako_artykul():
    """Wydawnictwo ciągłe NIE jest automatycznie artykułem naukowym.

    Ten sam model niesie streszczenia zjazdowe (PSZ, ZSZ), listy do redakcji
    (L), recenzje (R) i komunikaty (KOM). Charakter formalny bez ``rodzaj_pbn``
    znaczy, że rekord nie jedzie do PBN — a więc nie jest osiągnięciem z § 2
    ust. 10 pkt 4 i raport nie ma prawa żądać od niego DOI, ISSN ani flagi
    „czy artykuł recenzyjny”.
    """
    artykul = _artykul_z_autorem()
    streszczenie = _artykul_z_autorem(rodzaj_pbn=None)

    znalezione = _pk(selektory.powiazania(Osiagniecie.ARTYKUL))

    assert znalezione == {artykul.pk}
    assert streszczenie.pk not in znalezione


@pytest.mark.django_db
def test_ciagle_o_rodzaju_pbn_innym_niz_artykul_nie_jest_audytowane():
    """Pkt 4 mówi o *artykule naukowym*, a nie o dowolnym rekordzie w PBN."""
    ksiazkowe = _artykul_z_autorem(rodzaj_pbn=RODZAJ_PBN_KSIAZKA)

    assert _pk(selektory.powiazania(Osiagniecie.ARTYKUL)) == set()
    assert ksiazkowe.pk not in _pk(selektory.powiazania(Osiagniecie.ARTYKUL))


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


@pytest.mark.django_db
def test_dane_oa_bez_trybu_dostepu_daja_brak_zamiast_ciszy():
    """Regresja: pierwszy tiret lit. l to sam TRYB dostępu.

    Rekord z wypełnioną datą udostępnienia, ale bez trybu, wersji i licencji
    dawał wcześniej ZERO naruszeń: cztery reguły OA były bramkowane trybem,
    a piąta (miesiące) czasem udostępnienia — więc brak trybu wyłączał je
    wszystkie i raport milczał o danej zaczętej i niedokończonej.
    """
    powiazanie = _artykul_z_autorem()
    rekord = powiazanie.rekord
    rekord.openaccess_tryb_dostepu = None
    rekord.openaccess_wersja_tekstu = None
    rekord.openaccess_licencja = None
    rekord.openaccess_data_opublikowania = datetime.date(ROK, 3, 1)
    rekord.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert getattr(wiersz, selektory.pole_reguly("ART_OA_TRYB")) is True
    assert "ART_OA_TRYB" in {
        r.kod for r in selektory.naruszone_reguly(wiersz, Osiagniecie.ARTYKUL)
    }


@pytest.mark.django_db
def test_liczba_miesiecy_bramkowana_tak_samo_jak_reszta_litery():
    """Bez trybu dostępu ``*_OA_MIESIACE`` milczy — jak pozostałe reguły OA.

    Wcześniej ta jedna reguła bramkowana była wyłącznie skrótem czasu
    udostępnienia, więc rekord bez trybu dostawał brak liczby miesięcy
    i NIE dostawał braku wersji tekstu — dwie reguły tej samej litery mówiły
    co innego o tym samym rekordzie.
    """
    from bpp.models import Czas_Udostepnienia_OpenAccess

    czas, _ = Czas_Udostepnienia_OpenAccess.objects.get_or_create(
        skrot=OA_CZAS_PO_OPUBLIKOWANIU,
        defaults={"nazwa": "po opublikowaniu"},
    )

    powiazanie = _artykul_z_autorem()
    rekord = powiazanie.rekord
    rekord.openaccess_tryb_dostepu = None
    rekord.openaccess_czas_publikacji = czas
    rekord.openaccess_ilosc_miesiecy = None
    rekord.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert getattr(wiersz, selektory.pole_reguly("ART_OA_MIESIACE")) is False
    assert getattr(wiersz, selektory.pole_reguly("ART_OA_WERSJA")) is False
    # …a o samej dziurze mówi reguła od trybu dostępu.
    assert getattr(wiersz, selektory.pole_reguly("ART_OA_TRYB")) is True


# --------------------------------------------------------------------------
# Opłata za publikację (APC) — pokrycie bez dziur
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_zadeklarowana_oplata_bez_kwoty_jest_brakiem():
    """Regresja: luka między ``*_APC`` a ``*_APC_ZRODLO``.

    ``*_APC`` żądało, by wszystkie pięć pól było puste, ``*_APC_ZRODLO`` —
    kwoty dodatniej. Rekord z samym odznaczonym „bezkosztowa” wpadał między
    nie i nie naruszał NICZEGO, choć redaktor zadeklarował opłatę i nie podał
    ani jej kwoty, ani źródła.
    """
    powiazanie = _artykul_z_autorem()
    rekord = powiazanie.rekord
    rekord.opl_pub_cost_free = False
    rekord.opl_pub_amount = None
    rekord.opl_pub_research_potential = None
    rekord.opl_pub_research_or_development_projects = None
    rekord.opl_pub_other = None
    rekord.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert getattr(wiersz, selektory.pole_reguly("ART_APC_KWOTA")) is True
    assert getattr(wiersz, selektory.pole_reguly("ART_APC")) is False
    assert getattr(wiersz, selektory.pole_reguly("ART_APC_ZRODLO")) is False


@pytest.mark.django_db
def test_zadeklarowana_oplata_z_kwota_zerowa_tez_jest_brakiem():
    """Kwota 0 przy odznaczonej bezkosztowości jest wewnętrznie sprzeczna."""
    powiazanie = _artykul_z_autorem()
    rekord = powiazanie.rekord
    rekord.opl_pub_cost_free = False
    rekord.opl_pub_amount = Decimal("0")
    rekord.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert getattr(wiersz, selektory.pole_reguly("ART_APC_KWOTA")) is True


@pytest.mark.django_db
def test_publikacja_bezkosztowa_nie_wymaga_kwoty():
    """Zaznaczona bezkosztowość zamyka temat opłaty — bez żadnych braków."""
    _artykul_z_autorem()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    for kod in ("ART_APC", "ART_APC_KWOTA", "ART_APC_ZRODLO"):
        assert getattr(wiersz, selektory.pole_reguly(kod)) is False


# --------------------------------------------------------------------------
# Konferencja — § 2 ust. 10 pkt 4 lit. g
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_artykul_bez_konferencji_nie_generuje_brakow_konferencji():
    """„Nie opublikowano w materiałach konferencyjnych” to legalna odpowiedź."""
    _artykul_z_autorem()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    for kod in (
        "ART_KONFERENCJA_NAZWA",
        "ART_KONFERENCJA_DATY",
        "ART_KONFERENCJA_MIEJSCE",
    ):
        assert getattr(wiersz, selektory.pole_reguly(kod)) is False


@pytest.mark.django_db
def test_wskazana_konferencja_bez_dat_i_miejsca_daje_braki():
    powiazanie = _artykul_z_autorem()
    rekord = powiazanie.rekord
    rekord.konferencja = baker.make(
        "bpp.Konferencja",
        nazwa="Konferencja testowa",
        rozpoczecie=None,
        zakonczenie=None,
        miasto="",
        panstwo="",
    )
    rekord.save()

    wiersz = selektory.z_regulami(
        selektory.powiazania(Osiagniecie.ARTYKUL), Osiagniecie.ARTYKUL
    ).get()

    assert getattr(wiersz, selektory.pole_reguly("ART_KONFERENCJA_NAZWA")) is False
    assert getattr(wiersz, selektory.pole_reguly("ART_KONFERENCJA_DATY")) is True
    assert getattr(wiersz, selektory.pole_reguly("ART_KONFERENCJA_MIEJSCE")) is True
