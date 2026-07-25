"""Widok zbiorczy raportu kompletności danych POL-on.

Tabela „autor → liczba rekordów z brakami, braki wymagane, braki warunkowe”,
posortowana malejąco po brakach wymaganych. Agregacja obejmuje **wszystkie
cztery** typy osiągnięć naraz: § 2 ust. 10 rozporządzenia umieszcza
osiągnięcia w wykazie *pracowników*, więc jednostką, o którą pyta użytkownik,
jest osoba, a nie typ publikacji.
"""

from collections import defaultdict

from django.apps import apps
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.views.generic import TemplateView

from bpp.models import Autor
from bpp.util.uczelnia_scope import scope_autorzy_do_uczelni
from kompletnosc_polon.const import Osiagniecie
from kompletnosc_polon.selektory import (
    MODEL_POWIAZANIA,
    POLE_BRAKI_WARUNKOWE,
    POLE_BRAKI_WYMAGANE,
    powiazania,
    powiazania_nierozpoznane,
    z_regulami,
)

from .mixins import RaportKompletnosciMixin


def ma_jakikolwiek_brak() -> Q:
    """Warunek: wiersz narusza co najmniej jedną regułę — dowolnej wagi."""
    return Q(**{f"{POLE_BRAKI_WYMAGANE}__gt": 0}) | Q(
        **{f"{POLE_BRAKI_WARUNKOWE}__gt": 0}
    )


def sa_przypiete_dyscypliny(uczelnia=None) -> bool:
    """Czy istnieje choć jedno powiązanie z przypiętą dyscypliną.

    Pytanie zadajemy o **wszystkie lata**, nie o okno ewaluacji: chodzi
    o rozróżnienie „instalacja, w której nikt jeszcze nie przypisał
    dyscyplin” od „okno ewaluacji dopiero się otwiera, rekordów po prostu
    nie ma”. Te dwa stany dają identycznie pustą tabelę, a wymagają zupełnie
    innej reakcji użytkownika — dlatego widok komunikuje je osobno.

    Zawężamy natomiast do **uczelni oglądającego**: bez tego wartość logiczna
    zdradzałaby, czy dane ma jakakolwiek uczelnia w instalacji multi-tenant.
    Redaktor uczelni bez przypiętych dyscyplin zobaczyłby „raport nie ma czego
    sprawdzić”… albo i nie, w zależności od stanu bazy sąsiada — czyli jednym
    bitem wyciekłaby informacja o cudzych danych i zarazem wprowadziłaby go
    w błąd co do jego własnych.
    """
    for sciezka_modelu in set(MODEL_POWIAZANIA.values()):
        qs = apps.get_model(sciezka_modelu).objects.filter(
            przypieta=True, dyscyplina_naukowa__isnull=False
        )
        if scope_autorzy_do_uczelni(qs, uczelnia).exists():
            return True
    return False


def zbierz_po_autorach(uczelnia, okno) -> tuple[list[dict], int]:
    """Zsumuj braki po autorach, przez wszystkie typy osiągnięć.

    Zwraca krotkę: listę wierszy tabeli oraz liczbę **sprawdzonych** powiązań
    autor–rekord (także tych bez zastrzeżeń — bez niej pusta tabela nic nie
    znaczy, patrz „Obsługa błędów” w projekcie).

    Sumowanie idzie przez Pythona, nie przez ``GROUP BY``: querysety niosą już
    kilkanaście anotacji ``CASE`` na regułę, a ``values('autor_id')`` po
    ``annotate()`` wciągnęłoby je do grupowania. Z bazy ściągamy wyłącznie trzy
    liczby na wiersz (identyfikator autora i dwa liczniki), więc koszt jest
    proporcjonalny do liczby *niekompletnych* powiązań — a projekt zakłada, że
    zbiór jest mały (okno 2026+ dopiero się otwiera).
    """
    liczniki: dict[int, dict[str, int]] = defaultdict(
        lambda: {"rekordow": 0, "wymagane": 0, "warunkowe": 0}
    )
    sprawdzonych = 0

    for osiagniecie in Osiagniecie:
        qs = z_regulami(powiazania(osiagniecie, uczelnia, okno), osiagniecie)
        sprawdzonych += qs.count()

        for wiersz in qs.filter(ma_jakikolwiek_brak()).values(
            "autor_id", POLE_BRAKI_WYMAGANE, POLE_BRAKI_WARUNKOWE
        ):
            pozycja = liczniki[wiersz["autor_id"]]
            pozycja["rekordow"] += 1
            pozycja["wymagane"] += wiersz[POLE_BRAKI_WYMAGANE]
            pozycja["warunkowe"] += wiersz[POLE_BRAKI_WARUNKOWE]

    autorzy = Autor.objects.in_bulk(liczniki.keys())
    wiersze = [
        {
            "autor": autorzy[autor_id],
            "rekordow_z_brakami": pozycja["rekordow"],
            "braki_wymagane": pozycja["wymagane"],
            "braki_warunkowe": pozycja["warunkowe"],
        }
        for autor_id, pozycja in liczniki.items()
        if autor_id in autorzy
    ]
    wiersze.sort(
        key=lambda w: (
            -w["braki_wymagane"],
            -w["braki_warunkowe"],
            str(w["autor"]),
        )
    )
    return wiersze, sprawdzonych


def zbierz_nierozpoznane(uczelnia, okno) -> list[dict]:
    """Powiązania z rekordem, którego typu osiągnięcia nie da się ustalić.

    Grupujemy po autorze — inaczej użytkownik zobaczyłby, że coś jest nie tak,
    ale nie miałby jak do tego dojść: autor z samymi nierozpoznanymi rekordami
    nie pojawia się w głównej tabeli, bo nie ma dla niego czego policzyć.

    Tu agregujemy już w bazie: querysety nierozpoznanych nie przechodzą przez
    ``z_regulami``, więc nie niosą anotacji, które ``GROUP BY`` musiałby
    obsłużyć. Sumowanie po modelach idzie przez Pythona — selektor zwraca po
    jednym querysecie na model (zwarte, ciągłe), a ten sam autor może mieć
    nierozpoznane rekordy obu rodzajów i w tabeli ma być jednym wierszem.
    """
    zliczone: dict[int, int] = defaultdict(int)
    for qs in powiazania_nierozpoznane(uczelnia, okno):
        for pozycja in qs.values("autor_id").annotate(ile=Count("pk")):
            zliczone[pozycja["autor_id"]] += pozycja["ile"]

    autorzy = Autor.objects.in_bulk(zliczone.keys())
    wiersze = [
        {"autor": autorzy[autor_id], "rekordow": ile}
        for autor_id, ile in zliczone.items()
        if autor_id in autorzy
    ]
    wiersze.sort(key=lambda w: (-w["rekordow"], str(w["autor"])))
    return wiersze


class ListaKompletnosciView(RaportKompletnosciMixin, TemplateView):
    """Zbiorcze zestawienie braków — jeden wiersz na autora."""

    template_name = "kompletnosc_polon/lista.html"

    #: Autorów na stronę. Prawie każde powiązanie ma jakiś brak wymagany
    #: (``pbn_czy_*`` i ``opl_pub_*`` mają ``default=None``), więc bez
    #: paginacji tabela urosłaby do wiersza na każdego pracownika uczelni.
    autorow_na_stronie = 25

    def _stronicuj(self, wiersze, kontekst):
        """Podziel gotową listę wierszy na strony.

        Paginujemy listę Pythona, nie queryset: wiersze powstają przez
        zsumowanie braków z czterech typów osiągnięć (patrz
        :func:`zbierz_po_autorach`), więc nie ma jednego queryseta, który
        dałoby się przekazać ``ListView``. Nazwy w kontekście trzymamy takie,
        jakich oczekuje wspólny szablon ``pagination/pagination_with_anchor``.
        """
        paginator = Paginator(wiersze, self.autorow_na_stronie)
        strona = paginator.get_page(self.request.GET.get("page"))

        kontekst["paginator"] = paginator
        kontekst["page_obj"] = strona
        kontekst["is_paginated"] = strona.has_other_pages()
        kontekst["autorow"] = paginator.count
        return list(strona.object_list)

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)

        wiersze, sprawdzonych = zbierz_po_autorach(self.uczelnia, self.okno)
        kontekst["wiersze"] = self._stronicuj(wiersze, kontekst)
        kontekst["sprawdzonych"] = sprawdzonych
        kontekst["nierozpoznane"] = zbierz_nierozpoznane(self.uczelnia, self.okno)

        # Pytanie o dyscypliny zadajemy TYLKO wtedy, gdy raport nie miał czego
        # sprawdzić — przy niepustym zbiorze odpowiedź i tak jest twierdząca,
        # a zapytanie byłoby czystym kosztem.
        kontekst["brak_przypietych_dyscyplin"] = sprawdzonych == 0 and (
            not sa_przypiete_dyscypliny(self.uczelnia)
        )
        return kontekst
