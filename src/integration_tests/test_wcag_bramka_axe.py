"""Bramka dostępności: axe-core na publicznych stronach BPP (WCAG faza 3).

Próg to ZERO naruszeń, bez pliku baseline — przy czternastu naprawianych
naruszeniach zapadka byłaby droższa niż sama naprawa.

WYMAGANIE WSTĘPNE: `make assets`. Bez niego nie ma `axe.min.js` w statykach
ani zbudowanego CSS, więc pomiar kontrastu byłby bez sensu.

CZEGO TA BRAMKA NIE POKRYWA. Zasięg to trzy strony odwiedzane przez testy
poniżej: strona autora, strona uczelni, graf powiązań. Zadanie 3 przyciemniło
szarości w 19 plikach SCSS, a ich powierzchnia jest dużo szersza niż te trzy
strony — jednostka, szczegóły pracy, rok, multiseek, paginator, komparator
publikacji PBN i inne widoki NIE są tu skanowane i nie mają żadnej innej
bramki axe. Zielony wynik tego modułu świadczy o WCAG 2.2 AA na trzech
zmierzonych stronach, nie o całym serwisie — przyszły audyt nie powinien
czytać „istnieje bramka axe" jako „1.4.3 jest pilnowane wszędzie".
"""

import warnings

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor, Uczelnia
from integration_tests import axe_helper
from powiazania_autorow.models import AuthorConnection

# Bramka NIE MOZE korzystac z automatycznego rerunu, ktory fixture `page`
# dokłada testom przegladarkowym. Naruszenie dostepnosci nie znika przy
# drugim podejsciu — jesli raz zapalilo, to jest realne. Rerun zamienilby
# je w migotanie i przepuscil.
pytestmark = pytest.mark.flaky(reruns=0)


@pytest.mark.django_db(transaction=True)
def test_axe_daje_sie_uruchomic(channels_live_server, page: Page, transactional_db):
    """Sanity dla samego harnessu: axe się wstrzykuje i coś ocenia.

    Osobny test od bramki, bo odpowiada na inne pytanie. Bramka mówi „brak
    naruszeń"; ten mówi „pomiar w ogóle się odbył". Bez niego zielona bramka
    mogłaby znaczyć, że axe się nie załadował.
    """
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    page.goto(
        f"{channels_live_server.url}{reverse('bpp:browse_autor', args=[autor.slug])}",
        wait_until="networkidle",
    )

    wynik = axe_helper.skanuj(page)

    ocenione = len(wynik["violations"]) + len(wynik["passes"])
    assert ocenione > 10, (
        f"axe ocenił tylko {ocenione} reguł — wygląda, jakby się nie "
        "uruchomił albo trafił na pustą stronę"
    )

    # Zabezpieczenie przed cichym zawężeniem zakresu: gdyby ktoś usunął np.
    # `wcag2aa` z `axe_helper.TAGI`, `ocenione > 10` powyżej zostałoby
    # zielone (inne reguły i tak dają grubo ponad 10), a `color-contrast`
    # (dowiedzione mutacją w Zadaniu 5) przestałoby być w ogóle ewaluowane —
    # połowa bramki znikłaby bezgłośnie. Te dwie rodziny muszą być wśród
    # ocenionych reguł niezależnie od tego, w którym koszyku wylądowały;
    # `incomplete` wchodzi do sumy, bo `color-contrast` regularnie tam ląduje
    # (półprzezroczyste tła, patrz spec fazy).
    ocenione_id = {
        r["id"] for r in wynik["violations"] + wynik["passes"] + wynik["incomplete"]
    }
    brakujace = {"color-contrast", "label"} - ocenione_id
    assert not brakujace, (
        f"axe nie ewaluował reguł {brakujace} — zakres bramki (tagi WCAG) zwężony?"
    )

    # Asercja NIEZALEŻNA od dwóch powyższych: „ocenione > 10" i „obecność
    # rodzin color-contrast/label" łapią tylko połowę zawężenia zakresu.
    # Wykreślenie z `axe_helper.TAGI` np. `wcag21a`/`wcag21aa`/`wcag22a`/
    # `wcag22aa` zostawia `color-contrast` (`wcag2aa`) i `label` (`wcag2a`)
    # nietknięte — obie asercje wyżej pozostałyby zielone — a bezgłośnie
    # znikają reguły 2.1/2.2, w tym `target-size` (2.5.8), którą spec fazy
    # wymienia jako zmierzoną i zaliczoną. Dokładny zestaw pilnuje tego,
    # czego tamte dwie asercje nie widzą.
    assert axe_helper.TAGI == [
        "wcag2a",
        "wcag2aa",
        "wcag21a",
        "wcag21aa",
        "wcag22a",
        "wcag22aa",
    ], "zakres bramki (tagi WCAG) zwężony bez świadomej decyzji"


def _arkusz_motywu_zaladowany(page, motyw):
    """Sprawdza w `document.styleSheets`, że arkusz danego motywu wczytał
    się i realnie zawiera reguły.

    Bez tego HTTP 200 + sentinel nie dowodzą, że axe mierzy ostylowaną
    stronę: sentinel to klasa w HTML-u, nie reguła CSS, więc gdyby statyki
    przestały być serwowane (WhiteNoise, `STATIC_URL`, kolejność
    middleware), status i sentinel nadal byłyby zielone, a axe zmierzyłby
    czarny tekst na białym tle bez żadnego naruszenia kontrastu — a
    trzynaście z czternastu naruszeń naprawionych w tej fazie to właśnie
    kontrast. Wzorzec (sprawdzenie `document.styleSheets` po nazwie pliku
    `scss/<motyw>.css`) pochodzi z pomiaru sześciu motywów, patrz
    `docs/superpowers/specs/2026-08-13-wcag-stan-i-pozostale-prace.md`,
    sekcja „Kontrast w motywach". `cssRules.length > 0` odróżnia arkusz,
    który faktycznie się wczytał, od wpisu w `styleSheets`, który
    pozostaje nawet dla arkusza, którego żądanie sieciowe padło (pusty
    `CSSStyleSheet`).
    """
    return page.evaluate(
        """(motyw) => {
            const nazwa = `scss/${motyw}`;
            for (const arkusz of document.styleSheets) {
                if (!arkusz.href || !arkusz.href.includes(nazwa)) continue;
                try {
                    if (arkusz.cssRules.length > 0) return true;
                } catch (e) {
                    // SecurityError na arkuszach cross-origin — nie dotyczy
                    // naszych statyków serwowanych z tego samego hosta.
                }
            }
            return false;
        }""",
        motyw,
    )


def _sprawdz_strone(page, url, sentinel, nazwa, po_wejsciu=None, motyw="app-green"):
    """Otwiera stronę, sprawdza że to właściwa strona, skanuje, asertuje zero.

    Sentinel jest po to, żeby zielona bramka nie mogła znaczyć „trafiliśmy
    na 404". Wspólny `base.html` dziedziczy nawet strona błędu, więc sama
    obecność jakichkolwiek elementów niczego nie dowodzi.

    `motyw` jest po to, żeby zielona bramka nie mogła znaczyć „statyki
    przestały się ładować" — patrz `_arkusz_motywu_zaladowany`. Domyślny
    motyw testów to `app-green`.

    `po_wejsciu`, jeśli podane, jest wołane z `page` PO potwierdzeniu
    sentinela i PRZED skanem axe — miejsce na ustabilizowanie DOM-u stron
    z treścią losowaną przy każdym przebiegu (patrz strona uczelni).
    """
    odpowiedz = page.goto(url, wait_until="networkidle")

    assert odpowiedz is not None and odpowiedz.status == 200, (
        f"{nazwa}: status {odpowiedz.status if odpowiedz else '?'}, "
        "bramka mierzyłaby nie tę stronę"
    )
    assert page.locator(sentinel).count() > 0, (
        f"{nazwa}: brak sentinela {sentinel} — to nie jest ta strona"
    )
    assert _arkusz_motywu_zaladowany(page, motyw), (
        f"{nazwa}: arkusz stylów motywu '{motyw}' (scss/{motyw}.css) nie "
        "załadował się lub jest pusty — axe mierzyłby nieostylowaną stronę"
    )

    if po_wejsciu is not None:
        po_wejsciu(page)

    wynik = axe_helper.skanuj(page)

    # `warnings.warn`, NIE `print`: CI woła pytest bez `-s`, a pod xdistem
    # stdout przechodzącego testu jest odrzucany — zapis przez `print` był
    # iluzoryczny. Sekcja „warnings summary" pytest pokazuje ostrzeżenia
    # także dla przebiegów zielonych i przeżywa domyślne przechwytywanie
    # (potwierdzone empirycznie, patrz raport zadania). `incomplete` musi
    # być widoczne: naruszenie potrafi tam zmigrować (np. po zmianie tła
    # na półprzezroczyste) i zniknąć z pola widzenia bez tego zapisu.
    niejednoznaczne = axe_helper.opisz_niejednoznaczne(wynik)
    if niejednoznaczne != "incomplete: brak":
        warnings.warn(f"[{nazwa}] {niejednoznaczne}", stacklevel=2)

    assert wynik["violations"] == [], (
        f"{nazwa}: axe znalazł naruszenia WCAG 2.2 AA"
        + axe_helper.opisz_naruszenia(wynik)
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_strona_autora(channels_live_server, page: Page, transactional_db):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}{reverse('bpp:browse_autor', args=[autor.slug])}",
        ".autor-page__title-input",
        "strona autora",
    )


# `browse/uczelnia.html` losuje jedną z 15 porad w #rotating-tips na
# DOMContentLoaded i rotuje co 15s; trzy porady zawierają <a href>. Bez
# ustabilizowania test skanowałby losowy element DOM przy każdym przebiegu:
# realne naruszenie w treści porady byłoby wykrywane tylko w ułamku
# przebiegów, a defekt w jednej konkretnej poradzie zapalałby bramkę losowo
# (przy `pytestmark = flaky(reruns=0)` to twarda, niedeterministyczna
# czerwień — dokładnie ten kształt, po którym zespoły wyłączają bramki).
#
# Rozwiązanie w dwóch krokach, oba w `add_init_script` (MUSI polecieć
# przed `page.goto`, żeby zdążyć przed inline `<script>` szablonu):
# 1. `Math.random` jest nadpisany, żeby zawsze zwracać 0. Skrypt szablonu
#    liczy `Math.floor(Math.random() * tips.length)` przy pierwszym
#    wywołaniu `getRandomTip()` (pusty `usedTips`), więc `0 * n == 0` daje
#    zawsze `tips[0]` — PRAWDZIWĄ pierwszą poradę z tablicy w szablonie,
#    nie jej duplikat wpisany w teście. Zmiana treści porady albo dodanie
#    szesnastej z wadliwym znacznikiem trafia więc pod skan tak samo jak
#    na produkcji.
# 2. `setInterval` jest owinięty, żeby zapamiętać id każdego wywołania —
#    `_ustabilizuj_porady_uczelni` (wołane PO wejściu na stronę) czyści te
#    interwały, żeby rotacja nie zmieniła treści w trakcie skanu axe.
# Region NIE jest wyłączony ze skanu — to prawdziwa treść produkcyjna,
# mierzona deterministycznie, a nie zastąpiona stringiem z testu.
_PRZECHWYC_INTERVAL_JS = """
    window.__bramka_intervals = [];
    const _setInterval = window.setInterval;
    window.setInterval = (fn, ms, ...args) => {
        const id = _setInterval(fn, ms, ...args);
        window.__bramka_intervals.push(id);
        return id;
    };
    Math.random = () => 0;
"""


def _ustabilizuj_porady_uczelni(page):
    """Czyści interwał rotacji porad; treść #tip-text jest już deterministyczna
    dzięki nadpisanemu w `_PRZECHWYC_INTERVAL_JS` `Math.random`.
    """
    page.evaluate(
        """() => {
            (window.__bramka_intervals || []).forEach(
                (id) => clearInterval(id)
            );
        }"""
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_strona_uczelni(channels_live_server, page: Page, transactional_db):
    uczelnia = baker.make(Uczelnia, nazwa="Uczelnia Testowa", skrot="UT")
    page.add_init_script(_PRZECHWYC_INTERVAL_JS)
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_uczelnia', args=[uczelnia.slug])}",
        ".uczelnia__tile-description",
        "strona uczelni",
        po_wejsciu=_ustabilizuj_porady_uczelni,
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_graf_powiazan(channels_live_server, page: Page, transactional_db):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    wsp = baker.make(Autor, imiona="Anna", nazwisko="Nowak", pokazuj=True)
    baker.make(
        AuthorConnection,
        primary_author=autor,
        secondary_author=wsp,
        shared_publications_count=3,
    )
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor_powiazania', args=[autor.pk])}",
        "#graf-nawigacja",
        "graf powiązań",
    )
