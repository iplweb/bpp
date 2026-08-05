"""Test klucza cache fragmentu `{% cache %}` panelu filtrów w adminie.

DLACZEGO to musi istnieć: `{% cache 300 admin_filters request.GET.items ... %}`
przekazywał do `vary_on` **generator**. `MultiValueDict.items` to funkcja
generatorowa, a szablon Django wywołuje przekazane atrybuty — do klucza
trafiał więc `str(<generator object ... at 0x7f...>)`, czyli ADRES na stercie.

To groźniejsze niż niestabilny `hash()`: tam cache nie trafiał, tu trafiał
w CUDZY wpis. CPython reużywa zwolniony adres, więc kolejne requesty z
RÓŻNYMI filtrami dostawały ten sam klucz i przez 300 s widziały panel
filtrów wyrenderowany dla innego zestawu parametrów.

Warunek odtworzenia kolizji: generator musi zostać ZWOLNIONY między
iteracjami (tak jak między kolejnymi requestami) — dopiero wtedy alokator
reużywa adres.
"""

from django.core.cache.utils import make_template_fragment_key
from django.http import QueryDict

QUERY_STRINGI = ["rok=2020", "rok=2025", "rok=2030"]

SCIEZKA = "/admin/bpp/wydawnictwo_ciagle/"
UZYTKOWNIK = "admin"


def _klucz(vary_wartosc):
    return make_template_fragment_key(
        "admin_filters", [vary_wartosc, SCIEZKA, UZYTKOWNIK]
    )


def test_rozne_filtry_daja_rozne_klucze():
    """Sedno naprawy: klucz MUSI zależeć od parametrów GET.

    Czerwony na starej wersji (`request.GET.items`): trzy różne query
    stringi dawały jeden klucz.
    """
    klucze = [_klucz(QueryDict(qs).urlencode()) for qs in QUERY_STRINGI]

    assert len(set(klucze)) == len(QUERY_STRINGI), (
        f"kolizja kluczy cache panelu filtrów: {klucze} — różne filtry "
        "trafiają w ten sam wpis cache"
    )


def test_ten_sam_filtr_daje_ten_sam_klucz():
    """Bez tego cache nigdy by nie trafiał (klucz musi być stabilny)."""
    assert _klucz(QueryDict("rok=2020&typ=1").urlencode()) == _klucz(
        QueryDict("rok=2020&typ=1").urlencode()
    )


def test_generator_jako_vary_on_koliduje():
    """Kontrola metody: dowód, że test wyżej ma zęby.

    Odtwarza STARĄ implementację w warunkach audytu — generator zwalniany
    między iteracjami, jak między kolejnymi requestami. Jeśli to kiedyś
    przestanie kolidować, `test_rozne_filtry_daja_rozne_klucze` przechodzi
    również na zepsutym kodzie i nic nie sprawdza.
    """
    klucze = []
    for qs in QUERY_STRINGI:
        # `.items()` na MultiValueDict zwraca generator — dokładnie to, co
        # szablon podawał do vary_on. Nie trzymamy referencji, więc obiekt
        # jest zwalniany przed następną iteracją.
        klucze.append(_klucz(QueryDict(qs).items()))

    assert len(set(klucze)) < len(QUERY_STRINGI), (
        "generator w vary_on przestał kolidować — metodyka testu kolizji "
        "jest nieważna, popraw ją zanim uwierzysz w zielony wynik"
    )


def test_szablon_nie_uzywa_generatora_w_vary_on():
    """Regresja: szablon nie może wrócić do `request.GET.items`."""
    import pathlib

    import django_bpp

    szablon = (
        pathlib.Path(django_bpp.__file__).parent
        / "templates"
        / "admin"
        / "change_list.html"
    )
    tresc = szablon.read_text(encoding="utf-8")

    linie_cache = [
        linia
        for linia in tresc.splitlines()
        if "{% cache" in linia and "admin_filters" in linia
    ]
    assert linie_cache, "nie znaleziono tagu {% cache %} panelu filtrów"

    for linia in linie_cache:
        assert "request.GET.items" not in linia, (
            "vary_on znowu dostaje generator (`request.GET.items`) — klucz "
            "powstanie z adresu w pamięci i będzie kolidował"
        )
        assert "request.GET.urlencode" in linia
