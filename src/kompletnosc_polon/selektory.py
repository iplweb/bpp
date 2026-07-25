"""Budowa querysetów raportu kompletności danych POL-on.

Ziarnem raportu jest **para (autor, rekord)**, czyli dokładnie jeden wiersz
*through-modelu* powiązania autora z publikacją (``Wydawnictwo_Ciagle_Autor``,
``Wydawnictwo_Zwarte_Autor``, ``Patent_Autor``). Wynika to z konstrukcji
§ 2 ust. 10 rozporządzenia: osiągnięcia trafiają do *wykazu pracowników*,
a każde niesie własną dyscyplinę i własne upoważnienie. Ten sam artykuł
dwóch współautorów to w POL-onie dwa wpisy.

Moduł wystawia trzy warstwy, składane przez widok:

1. :func:`powiazania` — surowe ziarno, zawężone do okna ewaluacji, do
   przypiętych powiązań i do uczelni oglądającego;
2. :func:`z_regulami` — anotacja: po jednym ``BooleanField`` na regułę plus
   liczniki braków wymaganych i warunkowych;
3. :func:`naruszone_reguly` — odczyt anotacji z pojedynczego wiersza jako
   listy obiektów :class:`~kompletnosc_polon.reguly.Regula` (z opisem
   i podstawą prawną, do wyświetlenia).

Rozbieżności wobec projektu (świadome, opisane)
===============================================

*Zawężenie „przypięta dyscyplina”* realizujemy jako ``przypieta=True``
i **nie** dokładamy ``dyscyplina_naukowa__isnull=False``. Projekt w sekcji
„Przepływ danych” wymienia oba warunki, ale drugi z nich unieważniłby reguły
``*_DYSCYPLINA`` (``dyscyplina_naukowa`` NULL **lub** ``przypieta=False``) —
powiązanie bez dyscypliny wypadałoby z raportu, zamiast zostać w nim
zgłoszone jako brak. Zostawiamy więc w raporcie powiązania przypięte, ale
bezdyscyplinowe; człon ``przypieta=False`` reguł ``*_DYSCYPLINA`` jest przy
tym zawężeniu nieosiągalny i pozostaje wyłącznie jako dokumentacja wymogu.
"""

from functools import reduce

from django.apps import apps
from django.db.models import (
    BooleanField,
    Case,
    IntegerField,
    Q,
    QuerySet,
    Value,
    When,
)

from bpp.const import (
    CHARAKTER_SLOTY_KSIAZKA,
    CHARAKTER_SLOTY_ROZDZIAL,
    RODZAJ_PBN_ARTYKUL,
)
from bpp.util.uczelnia_scope import scope_autorzy_do_uczelni
from ewaluacja_common.const import OKNO_EWALUACJI
from kompletnosc_polon.const import Osiagniecie, Waga
from kompletnosc_polon.reguly import Regula, reguly_dla

#: Prefiks nazw anotacji z wynikiem reguły: ``brak_ART_DOI`` itd.
PREFIKS_POLA_REGULY = "brak_"

#: Nazwa anotacji z liczbą naruszonych reguł bezwarunkowych.
POLE_BRAKI_WYMAGANE = "braki_wymagane"

#: Nazwa anotacji z liczbą naruszonych reguł warunkowych („jeżeli posiada”).
POLE_BRAKI_WARUNKOWE = "braki_warunkowe"

#: Through-model niosący ziarno raportu dla danego typu osiągnięcia.
#: Monografia i rozdział dzielą jeden model — rozróżnia je dopiero
#: ``charakter_formalny.charakter_sloty`` (patrz :data:`FILTR_CHARAKTERU`).
MODEL_POWIAZANIA: dict[Osiagniecie, str] = {
    Osiagniecie.ARTYKUL: "bpp.Wydawnictwo_Ciagle_Autor",
    Osiagniecie.MONOGRAFIA: "bpp.Wydawnictwo_Zwarte_Autor",
    Osiagniecie.ROZDZIAL: "bpp.Wydawnictwo_Zwarte_Autor",
    Osiagniecie.PATENT: "bpp.Patent_Autor",
}

#: Zawężenie po charakterze formalnym rekordu — po jednym słowniku ``filter()``
#: na typ osiągnięcia. Patent nie ma charakteru formalnego w ogóle, więc go tu
#: nie ma.
#:
#: **Wydawnictwo ciągłe NIE jest automatycznie artykułem naukowym.** Ten sam
#: model niesie streszczenia zjazdowe (PSZ, ZSZ), listy do redakcji (L),
#: recenzje (R) i komentarze (KOM) — rzeczy, które nie są osiągnięciem z § 2
#: ust. 10 pkt 4 i nigdy nie jadą do PBN. Bez tego filtra raport żądał od nich
#: DOI, ISSN i flagi „czy artykuł recenzyjny”, zalewając listę brakami, których
#: nie ma po co uzupełniać.
#:
#: Kryterium jest ``Charakter_Formalny.rodzaj_pbn`` — to samo, którym posługuje
#: się reszta systemu przy pytaniu „czy ten rekord w ogóle jedzie do PBN”
#: (``pbn_integrator.utils.synchronization``, ``komparator_pbn.views``). Dla
#: ciągłych zawężamy je jeszcze mocniej, do :data:`RODZAJ_PBN_ARTYKUL`: pkt 4
#: mówi wprost o *artykule naukowym*, a wszystkie reguły ``ART_*`` (źródło,
#: ISSN, tom, strony, artykuł recenzyjny) są wymogami artykułu. Charakter
#: ciągły oznaczony jako rozdział albo książka byłby audytowany nie tą listą
#: wymogów, co trzeba.
#:
#: Wydawnictwo zwarte zostaje przy ``charakter_sloty``: to jedyne pole, które
#: rozróżnia monografię (pkt 5) od rozdziału (pkt 6), a ``rodzaj_pbn`` byłby
#: tu redundantny — w fixture instalacyjnym obie wartości idą w parze
#: (KS/KSP/KSZ/PA/SKR → książka, frg/ROZ/ROZS → rozdział). Nie dokładamy więc
#: drugiego warunku, który mógłby tylko po cichu ukryć rekord jawnie
#: zaklasyfikowany jako książka.
#:
#: Uwaga o świeżej instalacji: fixture zostawia ``rodzaj_pbn`` pusty także dla
#: charakteru „AC — Artykuł w czasopismie”. Dopóki administrator go nie ustawi
#: (ten sam krok konfiguracji, bez którego nie działa eksport do PBN), raport
#: nie ma w ciągłych czego sprawdzać — i **nie wolno mu wtedy milczeć**:
#: powiązania z takim rekordem zbiera :func:`_nierozpoznane_ciagle` i pokazuje
#: sekcja „nierozpoznany typ osiągnięcia”.
FILTR_CHARAKTERU: dict[Osiagniecie, dict[str, int]] = {
    Osiagniecie.ARTYKUL: {
        "rekord__charakter_formalny__rodzaj_pbn": RODZAJ_PBN_ARTYKUL,
    },
    Osiagniecie.MONOGRAFIA: {
        "rekord__charakter_formalny__charakter_sloty": CHARAKTER_SLOTY_KSIAZKA,
    },
    Osiagniecie.ROZDZIAL: {
        "rekord__charakter_formalny__charakter_sloty": CHARAKTER_SLOTY_ROZDZIAL,
    },
}


def pole_reguly(kod: str) -> str:
    """Nazwa anotacji niosącej wynik reguły o podanym kodzie."""
    return f"{PREFIKS_POLA_REGULY}{kod}"


def _model(osiagniecie: Osiagniecie):
    return apps.get_model(MODEL_POWIAZANIA[osiagniecie])


def _zawez(qs, okno: tuple[int, int], uczelnia) -> QuerySet:
    """Wspólne zawężenie ziarna: okno ewaluacji, przypięcie, uczelnia.

    Okno jest przedziałem **domkniętym** — oba lata graniczne wchodzą.

    Uczelnię odsiewamy przez ``scope_autorzy_do_uczelni``: through-modele
    niosą ``jednostka``, dokładnie tak jak mat-view autorstw, dla którego ten
    pomocnik powstał, więc reguła atrybucji (jednostka zapisana na autorstwie)
    i guard single-install są wspólne z resztą systemu — nie powielamy ich
    tutaj własnym filtrem.
    """
    pierwszy_rok, ostatni_rok = okno
    qs = qs.filter(
        rekord__rok__gte=pierwszy_rok,
        rekord__rok__lte=ostatni_rok,
        przypieta=True,
    )
    return scope_autorzy_do_uczelni(qs, uczelnia)


def powiazania(
    osiagniecie: Osiagniecie,
    uczelnia=None,
    okno: tuple[int, int] = OKNO_EWALUACJI,
) -> QuerySet:
    """Ziarno raportu dla jednego typu osiągnięcia.

    :param osiagniecie: typ osiągnięcia w rozumieniu § 2 ust. 10.
    :param uczelnia: uczelnia oglądającego; ``None`` (albo instalacja
        jednouczelniana) oznacza brak zawężenia.
    :param okno: domknięty przedział lat; domyślnie bieżące okno ewaluacji.
    """
    qs = _zawez(_model(osiagniecie).objects.all(), okno, uczelnia)

    filtr_charakteru = FILTR_CHARAKTERU.get(osiagniecie)
    if filtr_charakteru is not None:
        qs = qs.filter(**filtr_charakteru)

    return qs


def _nierozpoznane_zwarte(uczelnia, okno: tuple[int, int]) -> QuerySet:
    """Powiązania z wydawnictwem zwartym, którego nie da się zaklasyfikować.

    Fixture instalacyjny BPP zostawia ``Charakter_Formalny.charakter_sloty``
    puste, a bez tej wartości nie wiadomo, czy rekord jest monografią (pkt 5),
    czy rozdziałem (pkt 6) — a więc których wymogów od niego oczekiwać.

    Zakres to iloczyn dwóch warunków:

    * ``charakter_sloty IS NULL`` — czyli *brak klasyfikacji*. Wydawnictwo
      zwarte oznaczone jako referat (``CHARAKTER_SLOTY_REFERAT``) jest
      zaklasyfikowane jawnie i po prostu nie należy do żadnego z punktów
      objętych raportem — to nie jest brak danych;
    * ``rodzaj_pbn IS NOT NULL`` — czyli rekord, który **naprawdę jedzie do
      PBN**. Bez tego warunku sekcja zbierała charaktery sklasyfikowane
      poprawnie i celowo (frg, TŁ, SKR, PZ, BR, IN): migracje ``0173``
      i ``0225`` ustawiają ``charakter_sloty`` wyłącznie dla KS/KSP/KSZ,
      ROZ/ROZS i PRZ/ZRZ, więc pusta wartość jest normą, a nie usterką.
      Sekcja „raport tego nie sprawdził” ma zawierać wyłącznie rekordy, dla
      których to zdanie jest zarzutem.
    """
    return _zawez(
        apps.get_model("bpp.Wydawnictwo_Zwarte_Autor").objects.filter(
            rekord__charakter_formalny__charakter_sloty__isnull=True,
            rekord__charakter_formalny__rodzaj_pbn__isnull=False,
        ),
        okno,
        uczelnia,
    )


def _nierozpoznane_ciagle(uczelnia, okno: tuple[int, int]) -> QuerySet:
    """Powiązania z wydawnictwem ciągłym o niesklasyfikowanym charakterze.

    :data:`FILTR_CHARAKTERU` zawęża ciągłe do
    ``rodzaj_pbn = RODZAJ_PBN_ARTYKUL`` i tak ma zostać — pkt 4 mówi wprost
    o *artykule naukowym*, więc streszczenia zjazdowe i listy do redakcji
    słusznie z raportu wypadają. Rzecz w tym, że ``rodzaj_pbn`` **nie jest
    ustawiane przez fixture instalacyjny** (patrz migracja ``0174``: wypełnia
    je z pól ``artykul_pbn``/``ksiazka_pbn``/``rozdzial_pbn`` istniejącej
    instalacji, a w słowniku dostarczanym z BPP wszystkie są puste).
    Dopóki administrator nie ustawi go dla charakteru „AC — Artykuł
    w czasopismie”, z raportu wypadają **wszystkie artykuły naraz** — a to
    dokładnie ten tryb awarii, którego być nie może: pusta tabela i licznik
    sprawdzonych powiązań, który artykułów nie obejmuje, czytają się jak
    „artykuły są w porządku”.

    Warunkiem jest samo ``rodzaj_pbn IS NULL``, czyli *brak rozstrzygnięcia*
    — nie da się go tu podeprzeć drugim sygnałem tak, jak przy zwartych
    (``charakter_sloty``): dla ciągłych żadne inne pole charakteru nie mówi,
    czy rekord jest artykułem naukowym.

    Świadoma cena: pusta wartość jest zarazem legalnym wyborem „nie
    eksportuj do PBN” (etykieta ``None`` w ``choices``), więc do sekcji trafią
    także poprawnie oznaczone PSZ, ZSZ, L, R i KOM. Fałszywy alarm jest tu
    tańszy niż cisza — mówi „raport tego nie sprawdził” o rekordzie, którego
    faktycznie nie sprawdził, a zamyka się go jednym ustawieniem w słowniku
    charakterów formalnych.
    """
    return _zawez(
        apps.get_model("bpp.Wydawnictwo_Ciagle_Autor").objects.filter(
            rekord__charakter_formalny__rodzaj_pbn__isnull=True,
        ),
        okno,
        uczelnia,
    )


def powiazania_nierozpoznane(
    uczelnia=None,
    okno: tuple[int, int] = OKNO_EWALUACJI,
) -> list[QuerySet]:
    """Powiązania z rekordem, którego typu osiągnięcia nie da się ustalić.

    Takie powiązania wypadają ze wszystkich querysetów :func:`powiazania`
    i **nie wolno im zniknąć po cichu**, bo użytkownik uznałby, że raport je
    sprawdził i nie znalazł zastrzeżeń. Widok pokazuje je w jednej wspólnej
    sekcji „nierozpoznany typ osiągnięcia”.

    Zwracamy **listę querysetów**, po jednym na model: nierozpoznane bywają
    i wydawnictwa zwarte (brak ``charakter_sloty``, patrz
    :func:`_nierozpoznane_zwarte`), i ciągłe (brak ``rodzaj_pbn``, patrz
    :func:`_nierozpoznane_ciagle`), a to dwa różne through-modele, których
    jednym querysetem złączyć się nie da. Materializacji nie robimy tutaj —
    widok listy potrzebuje agregatu ``GROUP BY autor``, a widok szczegółów
    zawężenia do jednego autora; oba wykonują to na querysetach.
    """
    return [
        _nierozpoznane_zwarte(uczelnia, okno),
        _nierozpoznane_ciagle(uczelnia, okno),
    ]


def _czy_brakuje(warunek: Q):
    """Wyrażenie logiczne: czy warunek reguły zachodzi dla tego wiersza."""
    return Case(
        When(warunek, then=Value(True)),
        default=Value(False),
        output_field=BooleanField(),
    )


def _ile_brakow(reguly):
    """Suma naruszonych reguł — dodawanie wyrażeń, nie agregat.

    Świadomie NIE używamy ``Sum``: liczymy w obrębie jednego wiersza, więc
    agregat wymusiłby ``GROUP BY`` po całym through-modelu. Zwykłe dodawanie
    wyrażeń ``CASE ... THEN 1 ELSE 0`` daje ten sam wynik jednym przebiegiem.
    """
    skladniki = [
        Case(
            When(regula.warunek, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
        for regula in reguly
    ]
    if not skladniki:
        return Value(0, output_field=IntegerField())
    return reduce(lambda a, b: a + b, skladniki)


def z_regulami(qs: QuerySet, osiagniecie: Osiagniecie) -> QuerySet:
    """Dołóż anotacje z wynikiem każdej reguły danego typu osiągnięcia.

    Dokładane pola:

    * ``brak_<KOD>`` (``BooleanField``) — po jednym na regułę z
      :func:`~kompletnosc_polon.reguly.reguly_dla`; ``True`` znaczy „danej
      brakuje”;
    * :data:`POLE_BRAKI_WYMAGANE` i :data:`POLE_BRAKI_WARUNKOWE`
      (``IntegerField``) — liczba naruszonych reguł danej wagi.

    Queryset MUSI startować z through-modelu odpowiadającego typowi
    osiągnięcia (patrz :func:`powiazania`) — warunki reguł zapisane są od tej
    strony relacji.
    """
    reguly = reguly_dla(osiagniecie)

    anotacje = {pole_reguly(r.kod): _czy_brakuje(r.warunek) for r in reguly}
    anotacje[POLE_BRAKI_WYMAGANE] = _ile_brakow(
        [r for r in reguly if r.waga == Waga.WYMAGANE]
    )
    anotacje[POLE_BRAKI_WARUNKOWE] = _ile_brakow(
        [r for r in reguly if r.waga == Waga.WARUNKOWE]
    )

    return qs.annotate(**anotacje)


def naruszone_reguly(wiersz, osiagniecie: Osiagniecie) -> list[Regula]:
    """Reguły naruszone przez pojedynczy — zanotowany — wiersz raportu.

    Zwraca obiekty :class:`~kompletnosc_polon.reguly.Regula`, a nie same kody,
    bo widok szczegółów wypisuje z nich opis i podstawę prawną.

    :raises ValueError: gdy wiersz nie przeszedł przez :func:`z_regulami`.
        Cicha pusta lista byłaby tu najgorszą możliwą odpowiedzią — wyglądałaby
        jak „rekord kompletny”.
    """
    naruszone = []
    for regula in reguly_dla(osiagniecie):
        pole = pole_reguly(regula.kod)
        if not hasattr(wiersz, pole):
            raise ValueError(
                f"Wiersz {wiersz!r} nie ma anotacji {pole!r} — przepuść "
                f"queryset przez z_regulami(qs, {osiagniecie!r}) zanim "
                f"zapytasz o naruszone reguły."
            )
        if getattr(wiersz, pole):
            naruszone.append(regula)
    return naruszone
