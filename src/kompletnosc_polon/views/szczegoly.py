"""Widok szczegółów raportu kompletności danych POL-on — jeden autor.

Dla wskazanego autora wypisuje jego niekompletne rekordy, a przy każdym:
naruszone reguły (opis + podstawa prawna) oraz link prosto do formularza
edycji w panelu administracyjnym. To „prowadzenie do działania” jest sensem
raportu — sama informacja „czegoś brakuje” jest bezużyteczna, jeśli
uzupełnienie wymaga szukania rekordu po tytule.
"""

from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from bpp.models import Autor
from bpp.util.uczelnia_scope import scope_autor_do_uczelni
from kompletnosc_polon.const import Osiagniecie, Waga
from kompletnosc_polon.selektory import (
    POLE_BRAKI_WARUNKOWE,
    POLE_BRAKI_WYMAGANE,
    naruszone_reguly,
    powiazania,
    powiazania_nierozpoznane,
    z_regulami,
)

from .lista import ma_jakikolwiek_brak
from .mixins import RaportKompletnosciMixin, url_formularza_admina


def zbierz_pozycje(autor, uczelnia, okno) -> tuple[list[dict], int]:
    """Niekompletne rekordy jednego autora, z rozpisanymi brakami.

    Zwraca krotkę: listę pozycji oraz liczbę sprawdzonych powiązań tego
    autora — potrzebną, by przy zerze braków napisać wprost „sprawdzono N,
    brak zastrzeżeń”, zamiast pokazać pustą stronę.
    """
    pozycje = []
    sprawdzonych = 0

    for osiagniecie in Osiagniecie:
        qs = z_regulami(
            powiazania(osiagniecie, uczelnia, okno).filter(autor=autor),
            osiagniecie,
        )
        sprawdzonych += qs.count()

        niekompletne = (
            qs.filter(ma_jakikolwiek_brak())
            .select_related("rekord", "dyscyplina_naukowa", "jednostka")
            .order_by("-rekord__rok")
        )
        for wiersz in niekompletne:
            naruszone = naruszone_reguly(wiersz, osiagniecie)
            pozycje.append(
                {
                    "typ": osiagniecie.label,
                    "rekord": wiersz.rekord,
                    "dyscyplina": wiersz.dyscyplina_naukowa,
                    "jednostka": wiersz.jednostka,
                    "url_admina": url_formularza_admina(wiersz.rekord),
                    "wymagane": [r for r in naruszone if r.waga == Waga.WYMAGANE],
                    "warunkowe": [r for r in naruszone if r.waga == Waga.WARUNKOWE],
                    "braki_wymagane": getattr(wiersz, POLE_BRAKI_WYMAGANE),
                    "braki_warunkowe": getattr(wiersz, POLE_BRAKI_WARUNKOWE),
                }
            )

    pozycje.sort(key=lambda p: (-p["braki_wymagane"], -p["braki_warunkowe"]))
    return pozycje, sprawdzonych


def zbierz_nierozpoznane_autora(autor, uczelnia, okno) -> list[dict]:
    """Rekordy autora, których typu osiągnięcia nie da się ustalić.

    Wydawnictwo zwarte bez ``charakter_formalny.charakter_sloty`` może być
    monografią (pkt 5) albo rozdziałem (pkt 6); wydawnictwo ciągłe bez
    ``charakter_formalny.rodzaj_pbn`` — artykułem naukowym (pkt 4) albo
    publikacją, która osiągnięciem nie jest. W obu przypadkach nie wiadomo,
    których wymogów od rekordu oczekiwać: raport go NIE sprawdził i musi to
    powiedzieć wprost.

    Rekordy obu rodzajów lądują w **jednej** liście — użytkownika interesuje
    „czego raport nie sprawdził”, a nie z którego modelu to pochodzi. Rodzaj
    niesiemy per wiersz (``rodzaj``), bo od niego zależy, które pole słownika
    charakterów trzeba uzupełnić. Sortujemy w Pythonie, bo źródłem są dwa
    querysety.
    """
    pozycje = []
    for qs in powiazania_nierozpoznane(uczelnia, okno):
        wiersze = qs.filter(autor=autor).select_related(
            "rekord", "rekord__charakter_formalny"
        )
        pozycje.extend(
            {
                "rekord": wiersz.rekord,
                "rodzaj": wiersz.rekord._meta.verbose_name,
                "charakter_formalny": wiersz.rekord.charakter_formalny,
                "url_admina": url_formularza_admina(wiersz.rekord),
            }
            for wiersz in wiersze
        )
    pozycje.sort(key=lambda p: (-p["rekord"].rok, str(p["rekord"].tytul_oryginalny)))
    return pozycje


class SzczegolyKompletnosciView(RaportKompletnosciMixin, TemplateView):
    """Rozwinięcie zbiorczego zestawienia dla jednego autora."""

    template_name = "kompletnosc_polon/szczegoly.html"

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)

        # Autora szukamy w zbiorze JUŻ zawężonym do uczelni oglądającego.
        # Zawężenie samych powiązań nie wystarcza: slug jest przewidywalny
        # („nazwisko-imie”), więc bez tego superuser z ``?uczelnia=<nasza>``
        # dostawał HTTP 200 z imieniem i nazwiskiem pracownika OBCEJ uczelni
        # w tytule strony, okruszkach i nagłówku — czyli enumerację cudzej
        # kadry. Nieznalezienie autora w swojej uczelni ma być nieodróżnialne
        # od nieistnienia autora, stąd 404, a nie 200 z pustą listą.
        autor = get_object_or_404(
            scope_autor_do_uczelni(Autor.objects.all(), self.uczelnia),
            slug=self.kwargs["autor_slug"],
        )
        pozycje, sprawdzonych = zbierz_pozycje(autor, self.uczelnia, self.okno)

        kontekst["autor"] = autor
        kontekst["pozycje"] = pozycje
        kontekst["sprawdzonych"] = sprawdzonych
        kontekst["nierozpoznane"] = zbierz_nierozpoznane_autora(
            autor, self.uczelnia, self.okno
        )
        return kontekst
