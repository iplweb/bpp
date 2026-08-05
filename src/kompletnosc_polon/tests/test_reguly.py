"""Testy rejestru reguł kompletności danych POL-on.

Reguły są danymi, więc właściwą jednostką testową jest pojedyncza reguła.
Dla każdej z nich budujemy dwa powiązania autor–rekord: jedno spełniające
KOMPLET wymogów swojego typu osiągnięcia i jedno zepsute dokładnie w tym
jednym miejscu, którego reguła dotyczy. Asercja: ``warunek`` łapie wyłącznie
to zepsute.

Testy są parametryzowane po :data:`kompletnosc_polon.reguly.REGULY`, więc
dopisanie reguły bez dopisania sposobu jej zepsucia (:data:`PSUJ`) psuje
suitę — i o to chodzi.
"""

import datetime
import itertools
from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.const import RODZAJ_PBN_ARTYKUL
from kompletnosc_polon.const import OA_CZAS_PO_OPUBLIKOWANIU, Osiagniecie, Waga
from kompletnosc_polon.reguly import (
    REGULY,
    REGULY_ARTYKUL,
    REGULY_MONOGRAFIA,
    REGULY_PATENT,
    REGULY_ROZDZIAL,
    reguly_dla,
)

#: Rok wewnątrz bieżącego okna ewaluacji — patrz ``OKNO_EWALUACJI``.
ROK = 2026

#: Model powiązania autora z rekordem (ziarno raportu) dla każdego typu
#: osiągnięcia. Monografia i rozdział dzielą ten sam model — rozróżnia je
#: dopiero ``charakter_formalny.charakter_sloty``, czym zajmują się selektory,
#: nie reguły.
MODEL_POWIAZANIA = {
    Osiagniecie.ARTYKUL: "bpp.Wydawnictwo_Ciagle_Autor",
    Osiagniecie.MONOGRAFIA: "bpp.Wydawnictwo_Zwarte_Autor",
    Osiagniecie.ROZDZIAL: "bpp.Wydawnictwo_Zwarte_Autor",
    Osiagniecie.PATENT: "bpp.Patent_Autor",
}

MODEL_TRYBU_OA = {
    "wydawnictwo_ciagle": "bpp.Tryb_OpenAccess_Wydawnictwo_Ciagle",
    "wydawnictwo_zwarte": "bpp.Tryb_OpenAccess_Wydawnictwo_Zwarte",
}

_licznik_orcid = itertools.count(1)


def _kolejny_orcid() -> str:
    """Unikalny ORCID w formacie akceptowanym przez walidator ``Autor.orcid``."""
    numer = next(_licznik_orcid)
    return f"0000-0001-{numer // 10000 % 10000:04d}-{numer % 10000:04d}"


_licznik_dyscyplin = itertools.count(1)


def _kolejna_dyscyplina():
    """Dyscyplina naukowa o **deterministycznie** unikalnym kodzie.

    ``Dyscyplina_Naukowa.kod`` jest unikalny w bazie, a domyślny generator
    ``model_bakery`` losuje go z wąskiego zakresu (``N.MMM``). W teście
    budującym kilkadziesiąt powiązań naraz kolizja urodzinowa trafiała się na
    tyle często, że pełny przebieg suity potrafił paść na ``IntegrityError``
    w losowym miejscu. Licznik zamyka temat u źródła.
    """
    numer = next(_licznik_dyscyplin)
    return baker.make(
        "bpp.Dyscyplina_Naukowa",
        kod=f"{numer // 900 + 1}.{numer % 900 + 100}",
    )


# --------------------------------------------------------------------------
# Budowa obiektów kompletnych — takich, których ŻADNA reguła nie łapie
# --------------------------------------------------------------------------


def charakter_artykulu():
    """Charakter formalny, który raport uznaje za artykuł naukowy (pkt 4).

    Bez ``rodzaj_pbn = RODZAJ_PBN_ARTYKUL`` selektor :func:`powiazania`
    w ogóle nie wciągnie rekordu do raportu — tak samo, jak nie wciąga
    streszczeń zjazdowych, listów do redakcji czy recenzji.
    """
    return baker.make("bpp.Charakter_Formalny", rodzaj_pbn=RODZAJ_PBN_ARTYKUL)


def _kompletny_artykul():
    zrodlo = baker.make("bpp.Zrodlo", issn="1234-5678", e_issn="")
    return baker.make(
        "bpp.Wydawnictwo_Ciagle",
        rok=ROK,
        charakter_formalny=charakter_artykulu(),
        konferencja=None,
        zrodlo=zrodlo,
        doi="10.1000/kompletny",
        www="",
        public_www="",
        issn="",
        e_issn="",
        tom="12",
        informacje="",
        strony="1-10",
        szczegoly="",
        pbn_czy_artykul_recenzyjny=False,
        openaccess_tryb_dostepu=None,
        openaccess_wersja_tekstu=None,
        openaccess_licencja=None,
        openaccess_czas_publikacji=None,
        openaccess_data_opublikowania=None,
        openaccess_ilosc_miesiecy=None,
        opl_pub_cost_free=True,
        opl_pub_amount=None,
        opl_pub_research_potential=None,
        opl_pub_research_or_development_projects=None,
        opl_pub_other=None,
    )


def _kompletna_monografia_macierzysta():
    """Monografia macierzysta rozdziału, z kompletem danych identyfikujących.

    Reguły ``ROZ_MON_*`` sprawdzają ISBN/e-ISBN, wydawcę i DOI/URL rodzica,
    więc „kompletny” rozdział musi mieć rodzica, który je ma. Rodzic
    zbudowany gołym ``baker.make`` ma te pola puste i wywracałby test
    „żaden kompletny rekord nie jest łapany”.
    """
    return baker.make(
        "bpp.Wydawnictwo_Zwarte",
        rok=ROK,
        doi="10.1000/macierzysta",
        www="",
        public_www="",
        isbn="978-83-01-11111-1",
        e_isbn="",
        wydawca=baker.make("bpp.Wydawca"),
        wydawca_opis="",
        wydawnictwo_nadrzedne=None,
    )


def _kompletne_zwarte():
    """Wydawnictwo zwarte spełniające wymogi i monografii, i rozdziału."""
    return baker.make(
        "bpp.Wydawnictwo_Zwarte",
        rok=ROK,
        doi="10.1000/kompletny",
        www="",
        public_www="",
        isbn="978-83-01-00000-0",
        e_isbn="",
        wydawca=baker.make("bpp.Wydawca"),
        wydawca_opis="",
        wydawnictwo_nadrzedne=_kompletna_monografia_macierzysta(),
        wydawnictwo_nadrzedne_w_pbn=None,
        pbn_czy_edycja_naukowa=False,
        pbn_czy_projekt_ncn=False,
        pbn_czy_projekt_nprh=False,
        pbn_czy_projekt_fnp=False,
        pbn_czy_projekt_ue=False,
        openaccess_tryb_dostepu=None,
        openaccess_wersja_tekstu=None,
        openaccess_licencja=None,
        openaccess_czas_publikacji=None,
        openaccess_data_opublikowania=None,
        openaccess_ilosc_miesiecy=None,
        opl_pub_cost_free=True,
        opl_pub_amount=None,
        opl_pub_research_potential=None,
        opl_pub_research_or_development_projects=None,
        opl_pub_other=None,
    )


def _kompletny_patent():
    return baker.make(
        "bpp.Patent",
        rok=ROK,
        numer_prawa_wylacznego="PL 123456",
        numer_zgloszenia="P.400000",
        data_zgloszenia=datetime.date(ROK, 1, 15),
    )


BUDOWNICZY_REKORDU = {
    Osiagniecie.ARTYKUL: _kompletny_artykul,
    Osiagniecie.MONOGRAFIA: _kompletne_zwarte,
    Osiagniecie.ROZDZIAL: _kompletne_zwarte,
    Osiagniecie.PATENT: _kompletny_patent,
}


def _zbuduj_kompletne_powiazanie(osiagniecie: Osiagniecie):
    """Zbuduj parę (autor, rekord), której nie łapie żadna reguła.

    Zwraca instancję through-modelu — to jest ziarno raportu i jednocześnie
    punkt, z którego liczone są wszystkie warunki (patrz docstring modułu
    ``kompletnosc_polon.reguly``).
    """
    rekord = BUDOWNICZY_REKORDU[osiagniecie]()
    autor = baker.make("bpp.Autor", orcid=_kolejny_orcid())
    dyscyplina = _kolejna_dyscyplina()

    # Powiązanie autor–dyscyplina na dany rok jest wymuszone przez
    # BazaModeluOdpowiedzialnosciAutorow.clean(), wołane z save().
    baker.make(
        "bpp.Autor_Dyscyplina",
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina,
        subdyscyplina_naukowa=None,
    )

    return baker.make(
        MODEL_POWIAZANIA[osiagniecie],
        rekord=rekord,
        autor=autor,
        jednostka=baker.make("bpp.Jednostka"),
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        upowaznienie_pbn=True,
        oswiadczenie_ken=None,
    )


# --------------------------------------------------------------------------
# Psucie — jedna funkcja na regułę, wprowadza dokładnie jeden brak
# --------------------------------------------------------------------------


def _tryb_open_access(rekord):
    return baker.make(MODEL_TRYBU_OA[rekord._meta.model_name])


def _psuj_doi(powiazanie):
    rekord = powiazanie.rekord
    rekord.doi = None
    rekord.www = ""
    rekord.public_www = ""
    rekord.save()


def _psuj_dyscypline(powiazanie):
    powiazanie.przypieta = False
    powiazanie.save()


def _psuj_upowaznienie(powiazanie):
    powiazanie.upowaznienie_pbn = False
    powiazanie.save()


def _psuj_orcid(powiazanie):
    powiazanie.autor.orcid = None
    powiazanie.autor.save()


def _psuj_oa(pole):
    """Zbuduj funkcję psującą jedno pole Open Access.

    Ustawia tryb dostępu (czyli włącza wymogi OA) i czyści wskazane pole.
    """

    def psuj(powiazanie):
        rekord = powiazanie.rekord
        rekord.openaccess_tryb_dostepu = _tryb_open_access(rekord)
        setattr(rekord, pole, None)
        rekord.save()

    return psuj


def _psuj_oa_miesiace(powiazanie):
    from bpp.models import Czas_Udostepnienia_OpenAccess

    # Słownik czasów udostępnienia jest częścią baseline'u bazy (fixture
    # instalacyjny), a `skrot` ma ograniczenie unikalności — stąd
    # get_or_create zamiast baker.make.
    czas, _ = Czas_Udostepnienia_OpenAccess.objects.get_or_create(
        skrot=OA_CZAS_PO_OPUBLIKOWANIU,
        defaults={"nazwa": "po opublikowaniu"},
    )
    rekord = powiazanie.rekord
    # Tryb dostępu ustawiamy, bo reguła jest nim bramkowana tak samo jak
    # pozostałe reguły litery; bez trybu zadziałałaby ``*_OA_TRYB``.
    rekord.openaccess_tryb_dostepu = _tryb_open_access(rekord)
    rekord.openaccess_wersja_tekstu = baker.make("bpp.Wersja_Tekstu_OpenAccess")
    rekord.openaccess_licencja = baker.make("bpp.Licencja_OpenAccess")
    rekord.openaccess_data_opublikowania = datetime.date(ROK, 3, 1)
    rekord.openaccess_czas_publikacji = czas
    rekord.openaccess_ilosc_miesiecy = None
    rekord.save()


def _psuj_oa_tryb(powiazanie):
    """Wypełnij sygnał OA (datę udostępnienia), ale NIE podawaj trybu."""
    rekord = powiazanie.rekord
    rekord.openaccess_tryb_dostepu = None
    rekord.openaccess_data_opublikowania = datetime.date(ROK, 3, 1)
    rekord.save()


def _psuj_apc_kwota(powiazanie):
    """Odznacz „bezkosztowa”, ale nie podaj ani kwoty, ani źródła."""
    rekord = powiazanie.rekord
    rekord.opl_pub_cost_free = False
    rekord.opl_pub_amount = None
    rekord.opl_pub_research_potential = None
    rekord.opl_pub_research_or_development_projects = None
    rekord.opl_pub_other = None
    rekord.save()


def _konferencja(**nadpisz):
    """Konferencja z kompletem danych z lit. g, poza tym, co nadpisano."""
    pola = {
        "nazwa": "Konferencja testowa",
        "rozpoczecie": datetime.date(ROK, 5, 1),
        "zakonczenie": datetime.date(ROK, 5, 3),
        "miasto": "Lublin",
        "panstwo": "Polska",
    }
    pola.update(nadpisz)
    return baker.make("bpp.Konferencja", **pola)


def _psuj_konferencje(**nadpisz):
    """Zbuduj funkcję wskazującą konferencję z brakiem w podanych polach."""

    def psuj(powiazanie):
        rekord = powiazanie.rekord
        rekord.konferencja = _konferencja(**nadpisz)
        rekord.save()

    return psuj


def _psuj_pole_nadrzednego(**nadpisz):
    """Zbuduj funkcję psującą pola monografii macierzystej rozdziału."""

    def psuj(powiazanie):
        nadrzedne = powiazanie.rekord.wydawnictwo_nadrzedne
        for pole, wartosc in nadpisz.items():
            setattr(nadrzedne, pole, wartosc)
        nadrzedne.save()

    return psuj


def _psuj_apc(powiazanie):
    rekord = powiazanie.rekord
    rekord.opl_pub_cost_free = None
    rekord.opl_pub_amount = None
    rekord.opl_pub_research_potential = None
    rekord.opl_pub_research_or_development_projects = None
    rekord.opl_pub_other = None
    rekord.save()


def _psuj_apc_zrodlo(powiazanie):
    rekord = powiazanie.rekord
    rekord.opl_pub_cost_free = False
    rekord.opl_pub_amount = Decimal("1500.00")
    rekord.opl_pub_research_potential = None
    rekord.opl_pub_research_or_development_projects = False
    rekord.opl_pub_other = None
    rekord.save()


def _psuj_pole_rekordu(**nadpisz):
    """Zbuduj funkcję ustawiającą wskazane pola rekordu na podane wartości."""

    def psuj(powiazanie):
        rekord = powiazanie.rekord
        for pole, wartosc in nadpisz.items():
            setattr(rekord, pole, wartosc)
        rekord.save()

    return psuj


def _psuj_issn(powiazanie):
    rekord = powiazanie.rekord
    rekord.zrodlo.issn = ""
    rekord.zrodlo.e_issn = ""
    rekord.zrodlo.save()
    rekord.issn = ""
    rekord.e_issn = ""
    rekord.save()


#: Sposób wprowadzenia dokładnie tego braku, którego dotyczy dana reguła.
PSUJ = {
    # Artykuł naukowy — § 2 ust. 10 pkt 4
    "ART_DOI": _psuj_doi,
    "ART_DYSCYPLINA": _psuj_dyscypline,
    "ART_UPOWAZNIENIE": _psuj_upowaznienie,
    "ART_ORCID": _psuj_orcid,
    "ART_RECENZYJNY": _psuj_pole_rekordu(pbn_czy_artykul_recenzyjny=None),
    "ART_KONFERENCJA_NAZWA": _psuj_konferencje(nazwa=""),
    "ART_KONFERENCJA_DATY": _psuj_konferencje(zakonczenie=None),
    "ART_KONFERENCJA_MIEJSCE": _psuj_konferencje(panstwo=""),
    "ART_ZRODLO": _psuj_pole_rekordu(zrodlo=None),
    "ART_ISSN": _psuj_issn,
    "ART_TOM": _psuj_pole_rekordu(tom="", informacje=""),
    "ART_STRONY": _psuj_pole_rekordu(strony="", szczegoly=""),
    "ART_OA_TRYB": _psuj_oa_tryb,
    "ART_OA_WERSJA": _psuj_oa("openaccess_wersja_tekstu"),
    "ART_OA_LICENCJA": _psuj_oa("openaccess_licencja"),
    "ART_OA_DATA": _psuj_oa("openaccess_data_opublikowania"),
    "ART_OA_CZAS": _psuj_oa("openaccess_czas_publikacji"),
    "ART_OA_MIESIACE": _psuj_oa_miesiace,
    "ART_APC": _psuj_apc,
    "ART_APC_KWOTA": _psuj_apc_kwota,
    "ART_APC_ZRODLO": _psuj_apc_zrodlo,
    # Monografia naukowa — § 2 ust. 10 pkt 5
    "MON_DOI": _psuj_doi,
    "MON_ISBN": _psuj_pole_rekordu(isbn="", e_isbn=""),
    "MON_ORCID": _psuj_orcid,
    "MON_WYDAWCA": _psuj_pole_rekordu(wydawca=None, wydawca_opis=""),
    "MON_DYSCYPLINA": _psuj_dyscypline,
    "MON_UPOWAZNIENIE": _psuj_upowaznienie,
    "MON_EDYCJA_NAUKOWA": _psuj_pole_rekordu(pbn_czy_edycja_naukowa=None),
    "MON_PROJEKTY": _psuj_pole_rekordu(
        pbn_czy_projekt_ncn=None,
        pbn_czy_projekt_nprh=None,
        pbn_czy_projekt_fnp=None,
        pbn_czy_projekt_ue=None,
    ),
    "MON_OA_TRYB": _psuj_oa_tryb,
    "MON_OA_WERSJA": _psuj_oa("openaccess_wersja_tekstu"),
    "MON_OA_LICENCJA": _psuj_oa("openaccess_licencja"),
    "MON_OA_DATA": _psuj_oa("openaccess_data_opublikowania"),
    "MON_OA_CZAS": _psuj_oa("openaccess_czas_publikacji"),
    "MON_OA_MIESIACE": _psuj_oa_miesiace,
    "MON_APC": _psuj_apc,
    "MON_APC_KWOTA": _psuj_apc_kwota,
    "MON_APC_ZRODLO": _psuj_apc_zrodlo,
    # Rozdział w monografii — § 2 ust. 10 pkt 6
    "ROZ_NADRZEDNE": _psuj_pole_rekordu(
        wydawnictwo_nadrzedne=None, wydawnictwo_nadrzedne_w_pbn=None
    ),
    "ROZ_MON_ISBN": _psuj_pole_nadrzednego(isbn="", e_isbn=""),
    "ROZ_MON_WYDAWCA": _psuj_pole_nadrzednego(wydawca=None, wydawca_opis=""),
    "ROZ_MON_DOI": _psuj_pole_nadrzednego(doi=None, www="", public_www=""),
    "ROZ_ORCID": _psuj_orcid,
    "ROZ_DYSCYPLINA": _psuj_dyscypline,
    "ROZ_UPOWAZNIENIE": _psuj_upowaznienie,
    # Patent — § 2 ust. 10 pkt 1
    "PAT_NUMER": _psuj_pole_rekordu(numer_prawa_wylacznego=None),
    "PAT_ZGLOSZENIE": _psuj_pole_rekordu(data_zgloszenia=None),
    "PAT_DYSCYPLINA": _psuj_dyscypline,
    "PAT_UPOWAZNIENIE": _psuj_upowaznienie,
    "PAT_ORCID": _psuj_orcid,
}


def _id_reguly(regula):
    return regula.kod


# --------------------------------------------------------------------------
# Testy samego rejestru (bez bazy danych)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("regula", REGULY, ids=_id_reguly)
def test_regula_ma_komplet_metadanych(regula):
    assert regula.kod.strip(), "Reguła bez kodu"
    assert regula.opis.strip(), f"Reguła {regula.kod} bez opisu"
    assert regula.paragraf.strip(), f"Reguła {regula.kod} bez podstawy prawnej"
    assert regula.paragraf.startswith("§ 2 ust. 10 "), (
        f"Reguła {regula.kod} wskazuje paragraf spoza § 2 ust. 10"
    )
    assert regula.dotyczy in Osiagniecie
    assert regula.waga in Waga


def test_kody_regul_sa_unikalne():
    kody = [regula.kod for regula in REGULY]
    assert len(kody) == len(set(kody)), "Zduplikowane kody reguł w rejestrze"


@pytest.mark.parametrize("regula", REGULY, ids=_id_reguly)
def test_kod_reguly_pasuje_do_typu_osiagniecia(regula):
    prefiks = {
        Osiagniecie.ARTYKUL: "ART_",
        Osiagniecie.MONOGRAFIA: "MON_",
        Osiagniecie.ROZDZIAL: "ROZ_",
        Osiagniecie.PATENT: "PAT_",
    }[regula.dotyczy]
    assert regula.kod.startswith(prefiks)


@pytest.mark.parametrize("regula", REGULY, ids=_id_reguly)
def test_kazda_regula_ma_zdefiniowany_sposob_zepsucia(regula):
    assert regula.kod in PSUJ, (
        f"Dopisano regułę {regula.kod}, ale nie opisano, jak wprowadzić "
        f"brak, który ma łapać — uzupełnij słownik PSUJ."
    )


def test_reguly_dla_zwraca_rozlaczne_i_zupelne_podzbiory():
    zebrane = []
    for osiagniecie in Osiagniecie:
        podzbior = reguly_dla(osiagniecie)
        assert podzbior, f"Brak reguł dla {osiagniecie}"
        zebrane.extend(podzbior)

    assert len(zebrane) == len(REGULY)
    assert set(zebrane) == set(REGULY)


def test_rejestr_sklada_sie_z_czterech_grup():
    assert REGULY == (
        *REGULY_ARTYKUL,
        *REGULY_MONOGRAFIA,
        *REGULY_ROZDZIAL,
        *REGULY_PATENT,
    )


# --------------------------------------------------------------------------
# Test właściwy: reguła łapie brak i nie łapie kompletnego
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("regula", REGULY, ids=_id_reguly)
def test_regula_lapie_dokladnie_rekord_z_brakiem(regula):
    kompletne = _zbuduj_kompletne_powiazanie(regula.dotyczy)
    niekompletne = _zbuduj_kompletne_powiazanie(regula.dotyczy)

    PSUJ[regula.kod](niekompletne)

    model = type(niekompletne)
    znalezione = set(model.objects.filter(regula.warunek).values_list("pk", flat=True))

    assert znalezione == {niekompletne.pk}, (
        f"Reguła {regula.kod} ({regula.paragraf}) nie łapie wprowadzonego "
        f"braku albo łapie także rekord kompletny (pk={kompletne.pk})."
    )


@pytest.mark.django_db
@pytest.mark.parametrize("regula", REGULY, ids=_id_reguly)
def test_zaden_kompletny_rekord_nie_jest_lapany(regula):
    """Obiekt kompletny nie może być łapany przez ŻADNĄ regułę swojego typu.

    Chroni przed budowaniem „kompletnego” obiektu pod jedną regułę kosztem
    innej — a więc przed fałszywie zielonym testem powyżej.
    """
    kompletne = _zbuduj_kompletne_powiazanie(regula.dotyczy)
    model = type(kompletne)

    assert not model.objects.filter(regula.warunek).filter(pk=kompletne.pk).exists(), (
        f"Reguła {regula.kod} ({regula.paragraf}) łapie rekord kompletny."
    )


# --------------------------------------------------------------------------
# Alternatywy w koniunkcjach — „drugie źródło danej ratuje rekord”
#
# Testy wyżej psują WSZYSTKIE człony koniunkcji naraz, więc przechodzą także
# wtedy, gdy z warunku wypadnie dowolny człon poza pierwszym: rekord i tak
# zostanie złapany. Kod jest poprawny, ale suita tego nie broni. Poniższe
# testy domykają lukę od drugiej strony: psują człon główny, zostawiają
# wypełnioną alternatywę i wymagają, żeby reguła MILCZAŁA. Skasowanie
# któregokolwiek członu z warunku psuje któryś z nich.
# --------------------------------------------------------------------------

REGULA_PO_KODZIE = {regula.kod: regula for regula in REGULY}


def _lapie(kod: str, powiazanie) -> bool:
    """Czy reguła o podanym kodzie łapie to konkretne powiązanie."""
    warunek = REGULA_PO_KODZIE[kod].warunek
    return type(powiazanie).objects.filter(warunek).filter(pk=powiazanie.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("kod", ["ART_DOI", "MON_DOI"])
def test_publiczny_adres_www_zastepuje_doi(kod):
    """Lit. a żąda „identyfikatora cyfrowego”, nie konkretnie numeru DOI."""
    osiagniecie = REGULA_PO_KODZIE[kod].dotyczy
    powiazanie = _zbuduj_kompletne_powiazanie(osiagniecie)
    _psuj_pole_rekordu(doi=None, www="", public_www="https://example.org/publikacja")(
        powiazanie
    )

    assert not _lapie(kod, powiazanie)


@pytest.mark.django_db
def test_wewnetrzny_adres_www_zastepuje_doi():
    """Adres `www` (niepubliczny) też jest identyfikatorem cyfrowym."""
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.ARTYKUL)
    _psuj_pole_rekordu(doi=None, public_www="", www="https://intranet/x")(powiazanie)

    assert not _lapie("ART_DOI", powiazanie)


@pytest.mark.django_db
@pytest.mark.parametrize("pole", ["issn", "e_issn"])
def test_issn_na_samym_rekordzie_ratuje_artykul_bez_issn_zrodla(pole):
    """Numer wpisany przy rekordzie zastępuje pusty numer w słowniku źródeł."""
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.ARTYKUL)
    rekord = powiazanie.rekord
    rekord.zrodlo.issn = ""
    rekord.zrodlo.e_issn = ""
    rekord.zrodlo.save()
    setattr(rekord, pole, "1234-5678")
    rekord.save()

    assert not _lapie("ART_ISSN", powiazanie)


@pytest.mark.django_db
def test_e_issn_zrodla_ratuje_artykul_bez_issn():
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.ARTYKUL)
    rekord = powiazanie.rekord
    rekord.zrodlo.issn = ""
    rekord.zrodlo.e_issn = "8765-4321"
    rekord.zrodlo.save()

    assert not _lapie("ART_ISSN", powiazanie)


@pytest.mark.django_db
def test_pole_informacje_ratuje_pusty_tom():
    """Tom da się wyekstrahować z pola „Informacje” — to nie jest brak."""
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.ARTYKUL)
    _psuj_pole_rekordu(tom="", informacje="2026, vol. 12, nr 3")(powiazanie)

    assert not _lapie("ART_TOM", powiazanie)


@pytest.mark.django_db
def test_pole_szczegoly_ratuje_puste_strony():
    """Zakres stron da się wyekstrahować z pola „Szczegóły”."""
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.ARTYKUL)
    _psuj_pole_rekordu(strony="", szczegoly="s. 15-27")(powiazanie)

    assert not _lapie("ART_STRONY", powiazanie)


@pytest.mark.django_db
def test_e_isbn_ratuje_monografie_bez_isbn():
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.MONOGRAFIA)
    _psuj_pole_rekordu(isbn="", e_isbn="978-83-01-99999-9")(powiazanie)

    assert not _lapie("MON_ISBN", powiazanie)


@pytest.mark.django_db
def test_opis_wydawcy_ratuje_monografie_bez_wydawcy_ze_slownika():
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.MONOGRAFIA)
    _psuj_pole_rekordu(wydawca=None, wydawca_opis="Wydawnictwo Własne")(powiazanie)

    assert not _lapie("MON_WYDAWCA", powiazanie)


@pytest.mark.django_db
@pytest.mark.parametrize("kod", ["ART_APC_ZRODLO", "MON_APC_ZRODLO"])
@pytest.mark.parametrize(
    "flaga",
    [
        "opl_pub_research_potential",
        "opl_pub_research_or_development_projects",
        "opl_pub_other",
    ],
)
def test_kazde_zrodlo_finansowania_z_osobna_zamyka_wymog(kod, flaga):
    """Wystarczy JEDNO wskazane źródło — którekolwiek z trzech."""
    osiagniecie = REGULA_PO_KODZIE[kod].dotyczy
    powiazanie = _zbuduj_kompletne_powiazanie(osiagniecie)
    pola = {
        "opl_pub_cost_free": False,
        "opl_pub_amount": Decimal("1500.00"),
        "opl_pub_research_potential": None,
        "opl_pub_research_or_development_projects": None,
        "opl_pub_other": None,
    }
    pola[flaga] = True
    _psuj_pole_rekordu(**pola)(powiazanie)

    assert not _lapie(kod, powiazanie)


@pytest.mark.django_db
def test_brak_numeru_zgloszenia_lapie_patent_mimo_wpisanej_daty():
    """Drugi człon alternatywy z lit. g: numer, nie tylko data."""
    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.PATENT)
    assert powiazanie.rekord.data_zgloszenia is not None
    _psuj_pole_rekordu(numer_zgloszenia=None)(powiazanie)

    assert _lapie("PAT_ZGLOSZENIE", powiazanie)


@pytest.mark.django_db
def test_wydawnictwo_nadrzedne_w_pbn_ratuje_rozdzial_bez_rekordu_nadrzednego():
    """Rodzic wskazany w PBN zamyka lit. a tak samo jak rekord w BPP."""
    from pbn_api.models import Publication

    powiazanie = _zbuduj_kompletne_powiazanie(Osiagniecie.ROZDZIAL)
    _psuj_pole_rekordu(
        wydawnictwo_nadrzedne=None,
        wydawnictwo_nadrzedne_w_pbn=baker.make(Publication),
    )(powiazanie)

    assert not _lapie("ROZ_NADRZEDNE", powiazanie)
