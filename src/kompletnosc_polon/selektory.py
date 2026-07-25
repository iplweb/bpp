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

from bpp.const import CHARAKTER_SLOTY_KSIAZKA, CHARAKTER_SLOTY_ROZDZIAL
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
#: ``charakter_formalny.charakter_sloty`` (patrz :data:`CHARAKTER_SLOTOW`).
MODEL_POWIAZANIA: dict[Osiagniecie, str] = {
    Osiagniecie.ARTYKUL: "bpp.Wydawnictwo_Ciagle_Autor",
    Osiagniecie.MONOGRAFIA: "bpp.Wydawnictwo_Zwarte_Autor",
    Osiagniecie.ROZDZIAL: "bpp.Wydawnictwo_Zwarte_Autor",
    Osiagniecie.PATENT: "bpp.Patent_Autor",
}

#: Wartość ``Charakter_Formalny.charakter_sloty`` klasyfikująca wydawnictwo
#: zwarte do danego typu osiągnięcia. Typy spoza tego słownika (artykuł,
#: patent) nie podlegają klasyfikacji po charakterze formalnym: patent nie ma
#: takiego pola w ogóle, a wydawnictwo ciągłe jest zawsze pkt 4.
CHARAKTER_SLOTOW: dict[Osiagniecie, int] = {
    Osiagniecie.MONOGRAFIA: CHARAKTER_SLOTY_KSIAZKA,
    Osiagniecie.ROZDZIAL: CHARAKTER_SLOTY_ROZDZIAL,
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

    charakter_slotow = CHARAKTER_SLOTOW.get(osiagniecie)
    if charakter_slotow is not None:
        qs = qs.filter(rekord__charakter_formalny__charakter_sloty=charakter_slotow)

    return qs


def powiazania_nierozpoznane(
    uczelnia=None,
    okno: tuple[int, int] = OKNO_EWALUACJI,
) -> QuerySet:
    """Powiązania z wydawnictwem zwartym, którego nie da się zaklasyfikować.

    Fixture instalacyjny BPP zostawia ``Charakter_Formalny.charakter_sloty``
    puste, a bez tej wartości nie wiadomo, czy rekord jest monografią (pkt 5),
    czy rozdziałem (pkt 6) — a więc których wymogów od niego oczekiwać. Takie
    powiązania wypadają z obu querysetów :func:`powiazania` i **nie wolno im
    zniknąć po cichu**, bo użytkownik uznałby, że raport je sprawdził
    i nie znalazł zastrzeżeń. Widok pokazuje je w osobnej sekcji
    „nierozpoznany typ osiągnięcia”.

    Zakres celowo ograniczony do ``charakter_sloty IS NULL``, czyli do
    *braku klasyfikacji*. Wydawnictwo zwarte oznaczone jako referat
    (``CHARAKTER_SLOTY_REFERAT``) jest zaklasyfikowane jawnie i po prostu nie
    należy do żadnego z punktów objętych raportem — to nie jest brak danych.
    """
    return _zawez(
        apps.get_model("bpp.Wydawnictwo_Zwarte_Autor").objects.filter(
            rekord__charakter_formalny__charakter_sloty__isnull=True
        ),
        okno,
        uczelnia,
    )


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
