"""Rejestr reguł kompletności danych POL-on — reguły jako dane.

Każdy wymóg § 2 ust. 10 rozporządzenia MNiSW z 16 czerwca 2026 r. (Dz. U. 2026
poz. 811) zapisany jest jako jedna :class:`Regula` z warunkiem w postaci
``django.db.models.Q``. Dzięki temu jedna definicja obsługuje trzy
zastosowania: policzenie braków (``annotate``), zawężenie listy (``filter``)
oraz test jednostkowy. Dopisanie wymogu po nowelizacji to jeden wpis w
:data:`REGULY`, bez dotykania widoku.

Konwencja zapisu warunków (WAŻNE — selektory i widoki na niej polegają)
=======================================================================

**Warunki zapisane są od strony *through-modelu* powiązania autora z
rekordem**, czyli ``bpp.Wydawnictwo_Ciagle_Autor``,
``bpp.Wydawnictwo_Zwarte_Autor`` albo ``bpp.Patent_Autor``. Wynika to wprost
z ziarna raportu: § 2 ust. 10 umieszcza osiągnięcia w *wykazie pracowników*,
a każde osiągnięcie niesie własną dyscyplinę i własne upoważnienie. Jeden
wiersz raportu to jedna para (autor, rekord), czyli dokładnie jeden wiersz
through-modelu.

Stąd dwie klasy ścieżek pól:

* pola powiązania autora — **bez prefiksu**: ``dyscyplina_naukowa``,
  ``przypieta``, ``upowaznienie_pbn``, ``autor__orcid``;
* pola samej publikacji — z prefiksem :data:`PREFIKS_REKORDU` (``rekord__``):
  ``rekord__doi``, ``rekord__zrodlo__issn`` itd.

Projekt (``docs/superpowers/specs/2026-07-25-raport-kompletnosci-polon-2026-design.md``)
notował pola autora skrótem ``a__`` przy warunkach pisanych od strony modelu
konkretnego. Ta konwencja została świadomie odwrócona, bo:

1. ``a__`` nie jest realnym akcesorem Django — odwrotna relacja z
   ``Wydawnictwo_Ciagle`` do through-modelu nazywa się ``autorzy_set``;
2. warunek ``autorzy_set__upowaznienie_pbn=False`` na querysecie modelu
   konkretnego znaczy „*istnieje* autor bez upoważnienia”, a nie „*ten* autor
   nie ma upoważnienia” — a przy ``annotate()`` dodatkowo zwielokrotniałby
   wiersze przez JOIN;
3. sam projekt (sekcja „Przepływ danych”) zakłada, że selektory budują
   querysety through-modeli — czyli tę właśnie stronę relacji.

Warunek jest PRAWDZIWY, gdy danej BRAKUJE
=========================================

Konsekwentnie w całym rejestrze: reguła „łapie” rekord niekompletny. Pola
tekstowe w BPP są przeważnie ``blank=True, default=""`` (a więc NOT NULL),
ale nie wszystkie — ``doi``, ``autor.orcid``, ``numer_zgloszenia`` oraz
``numer_prawa_wylacznego`` dopuszczają NULL. Dlatego pustkę testujemy dwoma
pomocnikami: :func:`_puste` dla pól NOT NULL i :func:`_puste_lub_null` dla
pól nullowalnych. Warunki muszą dać się w całości wyrazić w SQL — żadnych
metod Pythona.
"""

from dataclasses import dataclass

from django.db.models import Q

from kompletnosc_polon.const import (
    OA_CZAS_PO_OPUBLIKOWANIU,
    Osiagniecie,
    Waga,
)

#: Prefiks ścieżki do pól publikacji, gdy zapytanie startuje z through-modelu
#: powiązania autora. Patrz docstring modułu.
PREFIKS_REKORDU = "rekord__"


@dataclass(frozen=True)
class Regula:
    """Pojedynczy wymóg rozporządzenia, wyrażony jako warunek SQL.

    :param kod: stabilny identyfikator, np. ``"ART_DOI"``; unikalny w całym
        rejestrze, używany w szablonach i w adresach URL.
    :param dotyczy: typ osiągnięcia, którego reguła dotyczy.
    :param warunek: ``Q`` prawdziwe wtedy i tylko wtedy, gdy danej BRAKUJE.
    :param opis: komunikat dla użytkownika — co konkretnie uzupełnić.
    :param paragraf: podstawa prawna, np. ``"§ 2 ust. 10 pkt 4 lit. a"``.
    :param waga: czy rozporządzenie żąda danej bezwarunkowo.
    """

    kod: str
    dotyczy: Osiagniecie
    warunek: Q
    opis: str
    paragraf: str
    waga: Waga = Waga.WYMAGANE


def _puste(pole: str) -> Q:
    """Pole tekstowe NOT NULL (``blank=True, default=""``) jest puste."""
    return Q(**{pole: ""})


def _puste_lub_null(pole: str) -> Q:
    """Pole tekstowe nullowalne jest puste albo NULL.

    W BPP nullowalne są m.in. ``doi`` (``DOIField(null=True)``),
    ``Autor.orcid``, ``Patent.numer_zgloszenia`` i
    ``Patent.numer_prawa_wylacznego`` — te dwa ostatnie z powodów
    historycznych (``# noqa: DJ001`` w modelu). Pusty ciąg i NULL znaczą
    dla użytkownika to samo: danej nie ma.
    """
    return Q(**{pole: ""}) | Q(**{f"{pole}__isnull": True})


def _nie_tak(pole: str) -> Q:
    """Nullowalne pole logiczne nie jest ustawione na „tak”.

    Zapisane wprost (``False`` albo NULL), zamiast przez ``~Q(pole=True)``,
    żeby wygenerowany SQL nie zależał od tego, jak Django obchodzi się
    z negacją warunku na kolumnie nullowalnej.
    """
    return Q(**{pole: False}) | Q(**{f"{pole}__isnull": True})


# --------------------------------------------------------------------------
# Fragmenty wspólne dla wielu typów osiągnięć
# --------------------------------------------------------------------------

#: Brak identyfikatora cyfrowego: ani DOI, ani żadnego adresu WWW.
#: ``doi`` jest nullowalne, ``www`` i ``public_www`` to ``URLField`` NOT NULL.
BRAK_IDENTYFIKATORA_CYFROWEGO = (
    _puste_lub_null("rekord__doi")
    & _puste("rekord__public_www")
    & _puste("rekord__www")
)

#: Dyscyplina nieokreślona albo odpięta od tego powiązania autor–rekord.
BRAK_DYSCYPLINY = Q(dyscyplina_naukowa__isnull=True) | Q(przypieta=False)

#: Autor nie upoważnił uczelni do sprawozdania tej publikacji.
#: ``upowaznienie_pbn`` to ``BooleanField(default=False)`` — NOT NULL.
BRAK_UPOWAZNIENIA = Q(upowaznienie_pbn=False)

#: Autor nie ma numeru ORCID. Pole ``Autor.orcid`` jest nullowalne (unique).
BRAK_ORCID = _puste_lub_null("autor__orcid")

#: Praca jest oznaczona jako Open Access. Wszystkie wymogi OA są warunkowe
#: względem tego oznaczenia: bez trybu dostępu rozporządzenie nie żąda
#: danych OA i raport milczy.
OZNACZONO_OPEN_ACCESS = Q(rekord__openaccess_tryb_dostepu__isnull=False)

#: Brak kompletu danych o opłacie za publikację (APC): nie wiadomo nawet,
#: czy publikacja była bezkosztowa.
BRAK_DANYCH_O_OPLACIE = (
    Q(rekord__opl_pub_cost_free__isnull=True)
    & Q(rekord__opl_pub_amount__isnull=True)
    & Q(rekord__opl_pub_research_potential__isnull=True)
    & Q(rekord__opl_pub_research_or_development_projects__isnull=True)
    & Q(rekord__opl_pub_other__isnull=True)
)

#: Wpisano kwotę opłaty, ale nie wskazano źródła jej finansowania.
BRAK_ZRODLA_OPLATY = (
    Q(rekord__opl_pub_amount__gt=0)
    & _nie_tak("rekord__opl_pub_research_potential")
    & _nie_tak("rekord__opl_pub_research_or_development_projects")
    & _nie_tak("rekord__opl_pub_other")
)


def _reguly_open_access(
    prefiks_kodu: str,
    dotyczy: Osiagniecie,
    paragraf: str,
) -> tuple[Regula, ...]:
    """Pięć reguł Open Access, identycznych dla artykułu i monografii.

    Wszystkie poza ``*_OA_MIESIACE`` są warunkowe względem ustawionego trybu
    dostępu. ``*_OA_MIESIACE`` uruchamia się węziej — tylko dla udostępnienia
    po opublikowaniu, bo tylko wtedy liczba miesięcy karencji ma sens.
    """
    return (
        Regula(
            kod=f"{prefiks_kodu}_OA_WERSJA",
            dotyczy=dotyczy,
            warunek=OZNACZONO_OPEN_ACCESS
            & Q(rekord__openaccess_wersja_tekstu__isnull=True),
            opis="Praca jest oznaczona jako Open Access, ale nie podano "
            "wersji udostępnionego tekstu.",
            paragraf=paragraf,
        ),
        Regula(
            kod=f"{prefiks_kodu}_OA_LICENCJA",
            dotyczy=dotyczy,
            warunek=OZNACZONO_OPEN_ACCESS & Q(rekord__openaccess_licencja__isnull=True),
            opis="Praca jest oznaczona jako Open Access, ale nie podano "
            "licencji, na jakiej ją udostępniono.",
            paragraf=paragraf,
        ),
        Regula(
            kod=f"{prefiks_kodu}_OA_DATA",
            dotyczy=dotyczy,
            warunek=OZNACZONO_OPEN_ACCESS
            & Q(rekord__openaccess_data_opublikowania__isnull=True),
            opis="Praca jest oznaczona jako Open Access, ale nie podano daty "
            "udostępnienia w otwartym dostępie.",
            paragraf=paragraf,
        ),
        Regula(
            kod=f"{prefiks_kodu}_OA_CZAS",
            dotyczy=dotyczy,
            warunek=OZNACZONO_OPEN_ACCESS
            & Q(rekord__openaccess_czas_publikacji__isnull=True),
            opis="Praca jest oznaczona jako Open Access, ale nie podano "
            "czasu udostępnienia (przed, w momencie albo po opublikowaniu).",
            paragraf=paragraf,
        ),
        Regula(
            kod=f"{prefiks_kodu}_OA_MIESIACE",
            dotyczy=dotyczy,
            warunek=Q(
                rekord__openaccess_czas_publikacji__skrot=OA_CZAS_PO_OPUBLIKOWANIU
            )
            & Q(rekord__openaccess_ilosc_miesiecy__isnull=True),
            opis="Pracę udostępniono po opublikowaniu, ale nie podano liczby "
            "miesięcy, jakie upłynęły od publikacji do udostępnienia.",
            paragraf=paragraf,
        ),
    )


def _reguly_oplaty(
    prefiks_kodu: str,
    dotyczy: Osiagniecie,
    paragraf: str,
) -> tuple[Regula, ...]:
    """Dwie reguły dotyczące opłaty za publikację (APC)."""
    return (
        Regula(
            kod=f"{prefiks_kodu}_APC",
            dotyczy=dotyczy,
            warunek=BRAK_DANYCH_O_OPLACIE,
            opis="Nie wypełniono danych o opłacie za publikację — nie "
            "zaznaczono nawet, czy publikacja była bezkosztowa.",
            paragraf=paragraf,
        ),
        Regula(
            kod=f"{prefiks_kodu}_APC_ZRODLO",
            dotyczy=dotyczy,
            warunek=BRAK_ZRODLA_OPLATY,
            opis="Wpisano kwotę opłaty za publikację, ale nie wskazano "
            "żadnego źródła jej finansowania.",
            paragraf=paragraf,
        ),
    )


# --------------------------------------------------------------------------
# Artykuł naukowy — § 2 ust. 10 pkt 4 — bpp.Wydawnictwo_Ciagle_Autor
# --------------------------------------------------------------------------

REGULY_ARTYKUL: tuple[Regula, ...] = (
    Regula(
        kod="ART_DOI",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=BRAK_IDENTYFIKATORA_CYFROWEGO,
        opis="Brak numeru DOI oraz adresu strony WWW artykułu.",
        paragraf="§ 2 ust. 10 pkt 4 lit. a",
    ),
    Regula(
        kod="ART_DYSCYPLINA",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=BRAK_DYSCYPLINY,
        opis="Autorowi nie przypisano dyscypliny naukowej dla tej pracy "
        "albo dyscyplina została odpięta.",
        paragraf="§ 2 ust. 10 pkt 4 lit. c",
    ),
    Regula(
        kod="ART_UPOWAZNIENIE",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=BRAK_UPOWAZNIENIA,
        opis="Brak upoważnienia autora do wykazania tej pracy w ewaluacji.",
        paragraf="§ 2 ust. 10 pkt 4 lit. d",
    ),
    Regula(
        kod="ART_ORCID",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=BRAK_ORCID,
        opis="Autor nie ma wpisanego identyfikatora ORCID.",
        paragraf="§ 2 ust. 10 pkt 4 lit. e",
        waga=Waga.WARUNKOWE,
    ),
    Regula(
        kod="ART_RECENZYJNY",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=Q(rekord__pbn_czy_artykul_recenzyjny__isnull=True),
        opis="Nie określono, czy artykuł jest artykułem recenzyjnym.",
        paragraf="§ 2 ust. 10 pkt 4 lit. f",
    ),
    Regula(
        kod="ART_ZRODLO",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=Q(rekord__zrodlo__isnull=True),
        opis="Nie wskazano czasopisma, w którym artykuł się ukazał.",
        paragraf="§ 2 ust. 10 pkt 4 lit. h",
    ),
    Regula(
        kod="ART_ISSN",
        dotyczy=Osiagniecie.ARTYKUL,
        # Gdy źródło nie jest wskazane, LEFT JOIN daje NULL-e i porównanie
        # z pustym ciągiem nie zadziała — stąd jawny człon o braku źródła.
        warunek=(
            Q(rekord__zrodlo__isnull=True)
            | (_puste("rekord__zrodlo__issn") & _puste("rekord__zrodlo__e_issn"))
        )
        & _puste("rekord__issn")
        & _puste("rekord__e_issn"),
        opis="Ani czasopismo, ani sam rekord nie mają numeru ISSN ani e-ISSN.",
        paragraf="§ 2 ust. 10 pkt 4 lit. h",
    ),
    Regula(
        kod="ART_TOM",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=_puste("rekord__tom") & _puste("rekord__informacje"),
        opis="Nie podano tomu (rocznika) czasopisma — pole „Tom” jest puste, "
        "a pole „Informacje” nie zawiera danych do wyekstrahowania.",
        paragraf="§ 2 ust. 10 pkt 4 lit. j",
        waga=Waga.WARUNKOWE,
    ),
    Regula(
        kod="ART_STRONY",
        dotyczy=Osiagniecie.ARTYKUL,
        warunek=_puste("rekord__strony") & _puste("rekord__szczegoly"),
        opis="Nie podano zakresu stron — pole „Strony” jest puste, a pole "
        "„Szczegóły” nie zawiera danych do wyekstrahowania.",
        paragraf="§ 2 ust. 10 pkt 4 lit. k",
        waga=Waga.WARUNKOWE,
    ),
    *_reguly_open_access("ART", Osiagniecie.ARTYKUL, "§ 2 ust. 10 pkt 4 lit. l"),
    *_reguly_oplaty("ART", Osiagniecie.ARTYKUL, "§ 2 ust. 10 pkt 4 lit. m"),
)


# --------------------------------------------------------------------------
# Monografia naukowa — § 2 ust. 10 pkt 5 — bpp.Wydawnictwo_Zwarte_Autor
# --------------------------------------------------------------------------

REGULY_MONOGRAFIA: tuple[Regula, ...] = (
    Regula(
        kod="MON_DOI",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=BRAK_IDENTYFIKATORA_CYFROWEGO,
        opis="Brak numeru DOI oraz adresu strony WWW monografii.",
        paragraf="§ 2 ust. 10 pkt 5 lit. a",
    ),
    Regula(
        kod="MON_ISBN",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=_puste("rekord__isbn") & _puste("rekord__e_isbn"),
        opis="Monografia nie ma numeru ISBN ani e-ISBN.",
        paragraf="§ 2 ust. 10 pkt 5 lit. b",
    ),
    Regula(
        kod="MON_ORCID",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=BRAK_ORCID,
        opis="Autor nie ma wpisanego identyfikatora ORCID.",
        paragraf="§ 2 ust. 10 pkt 5 lit. d",
        waga=Waga.WARUNKOWE,
    ),
    Regula(
        kod="MON_WYDAWCA",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=Q(rekord__wydawca__isnull=True) & _puste("rekord__wydawca_opis"),
        opis="Nie wskazano wydawcy monografii — ani ze słownika wydawców, ani opisowo.",
        paragraf="§ 2 ust. 10 pkt 5 lit. e",
    ),
    Regula(
        kod="MON_DYSCYPLINA",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=BRAK_DYSCYPLINY,
        opis="Autorowi nie przypisano dyscypliny naukowej dla tej pracy "
        "albo dyscyplina została odpięta.",
        paragraf="§ 2 ust. 10 pkt 5 lit. g",
    ),
    Regula(
        kod="MON_UPOWAZNIENIE",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=BRAK_UPOWAZNIENIA,
        opis="Brak upoważnienia autora do wykazania tej pracy w ewaluacji.",
        paragraf="§ 2 ust. 10 pkt 5 lit. h",
    ),
    Regula(
        kod="MON_EDYCJA_NAUKOWA",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=Q(rekord__pbn_czy_edycja_naukowa__isnull=True),
        opis="Nie określono, czy monografia jest edycją naukową tekstów źródłowych.",
        paragraf="§ 2 ust. 10 pkt 5 lit. j",
    ),
    Regula(
        kod="MON_PROJEKTY",
        dotyczy=Osiagniecie.MONOGRAFIA,
        warunek=Q(rekord__pbn_czy_projekt_ncn__isnull=True)
        & Q(rekord__pbn_czy_projekt_nprh__isnull=True)
        & Q(rekord__pbn_czy_projekt_fnp__isnull=True)
        & Q(rekord__pbn_czy_projekt_ue__isnull=True),
        opis="Nie określono, czy monografia powstała w ramach projektu NCN, "
        "NPRH, FNP lub finansowanego przez Unię Europejską.",
        paragraf="§ 2 ust. 10 pkt 5 lit. k",
    ),
    *_reguly_open_access("MON", Osiagniecie.MONOGRAFIA, "§ 2 ust. 10 pkt 5 lit. m"),
    *_reguly_oplaty("MON", Osiagniecie.MONOGRAFIA, "§ 2 ust. 10 pkt 5 lit. n"),
)


# --------------------------------------------------------------------------
# Rozdział w monografii — § 2 ust. 10 pkt 6 — bpp.Wydawnictwo_Zwarte_Autor
#
# Rozdział dziedziczy wymogi monografii macierzystej (lit. a odsyła do pkt 5),
# ale raport ich tu NIE duplikuje — braki monografii pokazuje przy monografii.
# Inaczej jedna niekompletna książka generowałaby braki przy każdym
# z kilkunastu rozdziałów, zalewając listę.
# --------------------------------------------------------------------------

REGULY_ROZDZIAL: tuple[Regula, ...] = (
    Regula(
        kod="ROZ_NADRZEDNE",
        dotyczy=Osiagniecie.ROZDZIAL,
        warunek=Q(rekord__wydawnictwo_nadrzedne__isnull=True)
        & Q(rekord__wydawnictwo_nadrzedne_w_pbn__isnull=True),
        opis="Nie wskazano monografii, w której rozdział się ukazał — ani "
        "rekordu w BPP, ani publikacji w PBN.",
        paragraf="§ 2 ust. 10 pkt 6 lit. a",
    ),
    Regula(
        kod="ROZ_ORCID",
        dotyczy=Osiagniecie.ROZDZIAL,
        warunek=BRAK_ORCID,
        opis="Autor nie ma wpisanego identyfikatora ORCID.",
        paragraf="§ 2 ust. 10 pkt 6 lit. c",
        waga=Waga.WARUNKOWE,
    ),
    Regula(
        kod="ROZ_DYSCYPLINA",
        dotyczy=Osiagniecie.ROZDZIAL,
        warunek=BRAK_DYSCYPLINY,
        opis="Autorowi nie przypisano dyscypliny naukowej dla tej pracy "
        "albo dyscyplina została odpięta.",
        paragraf="§ 2 ust. 10 pkt 6 lit. d",
    ),
    Regula(
        kod="ROZ_UPOWAZNIENIE",
        dotyczy=Osiagniecie.ROZDZIAL,
        warunek=BRAK_UPOWAZNIENIA,
        opis="Brak upoważnienia autora do wykazania tej pracy w ewaluacji.",
        paragraf="§ 2 ust. 10 pkt 6 lit. e",
    ),
)


# --------------------------------------------------------------------------
# Patent — § 2 ust. 10 pkt 1 — bpp.Patent_Autor
#
# Model Patent pokrywa tylko litery a, c, g oraz — przez relacje — k i m.
# Dla liter b, d, e, f, h, i, j, l BPP nie ma pól (nazwa uprawnionego,
# urząd udzielający, państwa ochrony, data ogłoszenia w „Wiadomościach Urzędu
# Patentowego", uprzednie pierwszeństwo, streszczenie opisu, data złożenia
# tłumaczenia patentu europejskiego). Raport nie może zgłaszać braku danej,
# dla której nie istnieje miejsce zapisu — por. FD#449.
# --------------------------------------------------------------------------

REGULY_PATENT: tuple[Regula, ...] = (
    Regula(
        kod="PAT_NUMER",
        dotyczy=Osiagniecie.PATENT,
        warunek=_puste_lub_null("rekord__numer_prawa_wylacznego"),
        opis="Nie podano numeru prawa wyłącznego (numeru patentu).",
        paragraf="§ 2 ust. 10 pkt 1 lit. c",
    ),
    Regula(
        kod="PAT_ZGLOSZENIE",
        dotyczy=Osiagniecie.PATENT,
        warunek=_puste_lub_null("rekord__numer_zgloszenia")
        | Q(rekord__data_zgloszenia__isnull=True),
        opis="Niekompletne dane zgłoszenia patentowego — brakuje numeru "
        "zgłoszenia albo jego daty.",
        paragraf="§ 2 ust. 10 pkt 1 lit. g",
    ),
    Regula(
        kod="PAT_DYSCYPLINA",
        dotyczy=Osiagniecie.PATENT,
        warunek=BRAK_DYSCYPLINY,
        opis="Współtwórcy nie przypisano dyscypliny naukowej dla tego "
        "patentu albo dyscyplina została odpięta.",
        paragraf="§ 2 ust. 10 pkt 1 lit. k",
    ),
    Regula(
        kod="PAT_UPOWAZNIENIE",
        dotyczy=Osiagniecie.PATENT,
        warunek=BRAK_UPOWAZNIENIA,
        opis="Brak upoważnienia współtwórcy do wykazania tego patentu w ewaluacji.",
        paragraf="§ 2 ust. 10 pkt 1 lit. l",
    ),
    Regula(
        kod="PAT_ORCID",
        dotyczy=Osiagniecie.PATENT,
        warunek=BRAK_ORCID,
        opis="Współtwórca nie ma wpisanego identyfikatora ORCID.",
        paragraf="§ 2 ust. 10 pkt 1 lit. m",
        waga=Waga.WARUNKOWE,
    ),
)


#: Kompletny rejestr reguł kompletności danych POL-on.
REGULY: tuple[Regula, ...] = (
    *REGULY_ARTYKUL,
    *REGULY_MONOGRAFIA,
    *REGULY_ROZDZIAL,
    *REGULY_PATENT,
)


def reguly_dla(osiagniecie: Osiagniecie) -> tuple[Regula, ...]:
    """Zwróć reguły dotyczące danego typu osiągnięcia."""
    return tuple(regula for regula in REGULY if regula.dotyczy == osiagniecie)
