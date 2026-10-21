# Naprawy WCAG stwierdzone lekturą kodu — plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Usunąć naruszenia WCAG 2.2 AA stwierdzone lekturą kodu (1.1.1 —
obrazy bez `alt`; 3.1.2 — brak atrybutów `lang` na tytułach obcojęzycznych)
bez budowania infrastruktury audytowej.

**Architecture:** Jeden filtr szablonowy `|oznacz_jezyk:` owija tytuł
oryginalny w `<span lang="…">` na podstawie `Jezyk.kod_bcp47`. Filtr jest
stosowany w czterech szablonach: dwóch renderujących stronę szczegółów
(efekt natychmiastowy) i dwóch będących wariantami generatora opisu
bibliograficznego (efekt po nocnym `denorm_rebuild`). Ponieważ opis
przechodzi przez sanityzator nh3 z wąską allowlistą, `span`/`lang` muszą
zostać do niej dopisane. Wstawienie znacznika do opisu psuje podświetlanie
w wyszukiwarce rekordów powiązanych (regex na surowym HTML) — logika
podświetlania zostaje wyekstrahowana do modułu JS i naprawiona.

**Tech Stack:** Django 5.x, szablony Django, pytest + model_bakery, nh3
(sanityzacja HTML), vitest (testy JS), towncrier (newsfragmenty).

**Spec:** `docs/superpowers/specs/2026-08-06-wcag-naprawy-stwierdzone-design.md`

## Global Constraints

- Wszystkie polecenia Pythona przez `uv run` — nigdy gołe `python`/`pytest`.
- Max długość linii Pythona: 88 znaków (ruff).
- Testy: pytest, funkcje (nie klasy), `@pytest.mark.django_db` dla bazy,
  `model_bakery.baker.make` do tworzenia obiektów.
- Komentarze w szablonach Django `{# … #}` **jedno-liniowe** — każda linia
  ma własne otwarcie i zamknięcie. Wieloliniowe wyciekają do HTML-u.
- **NIE modyfikować istniejących migracji** w `src/*/migrations/`.
- Praca w worktree `/Volumes/SSD/Programowanie/bpp-wcag-naprawy`, gałąź
  `fix-wcag-naprawy-stwierdzone`.
- Po zmianach uruchamiać testy lokalnie, nie zrzucać na CI.
- Newsfragmenty: `src/bpp/newsfragments/<slug>.<typ>.rst` — **nie**
  `changes/newsfragments/`.

## Struktura plików

**Tworzone:**

| plik | odpowiedzialność |
|---|---|
| `src/bpp/static/bpp/js/related-records-highlight.js` | czysta funkcja podświetlania omijająca znaczniki HTML |
| `tests/js/related-records-highlight.test.js` | testy vitest tej funkcji |
| `src/bpp/tests/test_templatetags/test_oznacz_jezyk.py` | testy filtru |
| `src/bpp/tests/test_wcag/__init__.py` | pakiet testów WCAG |
| `src/bpp/tests/test_wcag/test_lang_szablony.py` | 3.1.2 w szablonach stron |
| `src/bpp/tests/test_wcag/test_lang_opis.py` | 3.1.2 w generatorze opisu |
| `src/bpp/tests/test_wcag/test_alt_obrazy.py` | 1.1.1 |
| `src/bpp/tests/test_util/test_sanityzator_span_lang.py` | regresja bezpieczeństwa allowlisty |
| `src/pbn_export_queue/tests/test_wyszukiwanie_opisu.py` | substring-search w kolejce PBN |
| `src/bpp/newsfragments/wcag-lang-tytulow.feature.rst` | newsfragment |
| `src/bpp/newsfragments/wcag-alt-obrazow.bugfix.rst` | newsfragment |

**Modyfikowane:**

| plik | zmiana |
|---|---|
| `src/bpp/templatetags/prace.py` | dodanie filtru `oznacz_jezyk`, korekta docstringu `safe_tytul` |
| `src/bpp/util/text.py:306-313` | `span` + `lang` w allowliście opisu |
| `src/bpp/templates/browse/praca_tabela_mono.html` | `lang` na tytule, podpięcie modułu JS podświetlania |
| `src/bpp/templates/browse/praca.html` | `lang` w breadcrumbie |
| `src/bpp/templates/opis_bibliograficzny.html` | `lang` w generatorze (domyślny) |
| `src/bpp/templates/browse/praca_tabela.html` | `lang` w generatorze (wariant) |
| `src/bpp/templates/504.html` | `alt=""` |
| `docs/superpowers/specs/2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md` | korekty + wykaz odroczonych |

**Usuwane:**

- `src/bpp/templates/user_navigation_autocomplete.html` (martwy szablon)

---

### Task 1: Filtr `oznacz_jezyk`

Filtr owija wartość w `<span lang="…">` na podstawie obiektu `Jezyk`.
Stosowany **po** filtrach sanityzujących (`safe_tytul`, `safe`), bo sam nie
sanityzuje — tylko owija już bezpieczną wartość.

**Files:**
- Modify: `src/bpp/templatetags/prace.py`
- Test: `src/bpp/tests/test_templatetags/test_oznacz_jezyk.py`

**Interfaces:**
- Consumes: nic (pierwsze zadanie)
- Produces: filtr szablonowy `oznacz_jezyk` w bibliotece `prace`, sygnatura
  `oznacz_jezyk(wartosc, jezyk) -> str`. Zwraca `SafeString` z opakowaniem
  gdy `jezyk.kod_bcp47` jest niepuste; w każdym innym przypadku zwraca
  `wartosc` bez zmian. Używany w Task 3 i Task 4.

- [ ] **Step 1: Napisz test filtru**

Utwórz `src/bpp/tests/test_templatetags/test_oznacz_jezyk.py`:

```python
"""Filtr ``|oznacz_jezyk:`` — atrybut ``lang`` na tytule (WCAG 3.1.2).

Kryterium 3.1.2 wymaga oznaczenia fragmentu w innym języku niż język
strony. ``lang=""`` (pusty) jest GORSZY niż brak atrybutu: unieważnia
dziedziczenie z ``<html lang="pl">``, więc fragment, który bez atrybutu
zostałby odczytany poprawnie po polsku, staje się "językiem nieznanym".
Stąd wymóg, by przy braku danych atrybut nie pojawiał się wcale.
"""

import pytest
from django.template import Context, Template
from django.utils.safestring import SafeString, mark_safe

from bpp.templatetags.prace import oznacz_jezyk


class FakeJezyk:
    """Zastępnik ``Jezyk`` — filtr czyta wyłącznie ``kod_bcp47``."""

    def __init__(self, kod_bcp47):
        self.kod_bcp47 = kod_bcp47


def test_oznacz_jezyk_owija_gdy_kod_niepusty():
    assert oznacz_jezyk("Effects of X", FakeJezyk("en")) == (
        '<span lang="en">Effects of X</span>'
    )


def test_oznacz_jezyk_obsluguje_kod_regionalny():
    assert oznacz_jezyk("Colour", FakeJezyk("en-GB")) == (
        '<span lang="en-GB">Colour</span>'
    )


def test_oznacz_jezyk_pomija_atrybut_gdy_kod_pusty():
    wynik = oznacz_jezyk("Tytuł", FakeJezyk(""))
    assert wynik == "Tytuł"
    assert "lang=" not in wynik


def test_oznacz_jezyk_pomija_atrybut_gdy_brak_jezyka():
    wynik = oznacz_jezyk("Tytuł", None)
    assert wynik == "Tytuł"
    assert "<span" not in wynik


def test_oznacz_jezyk_pomija_atrybut_gdy_kod_to_none():
    assert oznacz_jezyk("Tytuł", FakeJezyk(None)) == "Tytuł"


def test_oznacz_jezyk_zachowuje_bezpieczny_html_wartosci():
    # Wartość po |safe_tytul jest SafeString z zamierzoną kursywą —
    # opakowanie nie może jej podwójnie zescape'ować.
    wartosc = mark_safe("Rola <i>Candida</i> w zakażeniach")
    assert oznacz_jezyk(wartosc, FakeJezyk("pl")) == (
        '<span lang="pl">Rola <i>Candida</i> w zakażeniach</span>'
    )


def test_oznacz_jezyk_escapuje_wartosc_niebezpieczna():
    # Gdyby filtr trafił na wartość NIE-safe (pominięty |safe_tytul),
    # nie wolno mu przepuścić surowego HTML-a.
    wynik = oznacz_jezyk("<script>alert(1)</script>", FakeJezyk("en"))
    assert "<script>" not in wynik
    assert "&lt;script&gt;" in wynik


def test_oznacz_jezyk_escapuje_kod_jezyka():
    # kod_bcp47 pochodzi ze słownika edytowalnego w adminie.
    wynik = oznacz_jezyk("Tytuł", FakeJezyk('en" onload="x'))
    assert 'onload="x"' not in wynik


def test_oznacz_jezyk_zwraca_safestring():
    assert isinstance(oznacz_jezyk("Tytuł", FakeJezyk("en")), SafeString)


@pytest.mark.parametrize(
    "kod,oczekiwany",
    [("en", '<span lang="en">Tytuł</span>'), ("", "Tytuł")],
)
def test_oznacz_jezyk_dziala_w_szablonie(kod, oczekiwany):
    tpl = Template(
        "{% load prace %}{{ tytul|oznacz_jezyk:jezyk }}"
    )
    wynik = tpl.render(Context({"tytul": "Tytuł", "jezyk": FakeJezyk(kod)}))
    assert wynik == oczekiwany
```

- [ ] **Step 2: Uruchom test — musi paść**

```bash
cd /Volumes/SSD/Programowanie/bpp-wcag-naprawy
uv run pytest src/bpp/tests/test_templatetags/test_oznacz_jezyk.py -v
```

Oczekiwane: `ImportError: cannot import name 'oznacz_jezyk'`.

- [ ] **Step 3: Zaimplementuj filtr**

W `src/bpp/templatetags/prace.py` dopisz na końcu pliku:

```python
@register.filter(name="oznacz_jezyk")
def oznacz_jezyk(wartosc, jezyk):
    """Owiń tytuł w ``<span lang="…">`` na podstawie ``Jezyk.kod_bcp47``.

    WCAG 2.2 AA, kryterium 3.1.2 (Language of Parts): tytuł obcojęzyczny na
    stronie ``lang="pl"`` musi nieść własny znacznik języka, inaczej czytnik
    ekranu odczyta go polską fonetyką.

    Gdy kod języka jest pusty (``kod_bcp47`` jest ``blank=True``) albo relacja
    ``jezyk`` nie istnieje, atrybut NIE jest dodawany. ``lang=""`` byłby
    gorszy niż jego brak: pusta wartość znaczy "język nieznany" i unieważnia
    dziedziczenie z ``<html lang="pl">``.

    Stosować jako filtr OSTATNI — po ``safe_tytul``/``safe``, bo te
    sanityzują wąską allowlistą, która ``<span>`` by wycięła.
    """
    kod = getattr(jezyk, "kod_bcp47", None)
    if not kod:
        return wartosc
    return format_html('<span lang="{}">{}</span>', kod, wartosc)
```

W nagłówku pliku dopisz import (obok istniejącego `mark_safe`):

```python
from django.utils.html import format_html
```

`format_html` respektuje `SafeString` (przez `conditional_escape`), więc
wartość po `|safe_tytul` przechodzi nietknięta, a wartość surowa zostaje
zescape'owana. Kod języka jest escape'owany zawsze.

- [ ] **Step 4: Uruchom test — musi przejść**

```bash
uv run pytest src/bpp/tests/test_templatetags/test_oznacz_jezyk.py -v
```

Oczekiwane: 11 passed.

- [ ] **Step 5: Popraw docstring `safe_tytul`**

`safe_tytul` (`src/bpp/templatetags/prace.py:120-131`) twierdzi „Stosować
jako OSTATNI filtr". Po dodaniu `oznacz_jezyk` to nieprawda. W docstringu
zamień zdanie:

```
    Stosować jako OSTATNI filtr (po ``truncatewords_html``/``znak_na_koncu``).
```

na:

```
    Stosować jako ostatni filtr SANITYZUJĄCY (po
    ``truncatewords_html``/``znak_na_koncu``). Wyjątek: ``oznacz_jezyk``
    idzie PO nim — tylko owija wynik, nie wnosi treści do sanityzacji.
```

- [ ] **Step 6: Sprawdź formatowanie i zacommituj**

```bash
uv run ruff format src/bpp/templatetags/prace.py \
    src/bpp/tests/test_templatetags/test_oznacz_jezyk.py
uv run ruff check src/bpp/templatetags/prace.py \
    src/bpp/tests/test_templatetags/test_oznacz_jezyk.py
git add src/bpp/templatetags/prace.py \
    src/bpp/tests/test_templatetags/test_oznacz_jezyk.py
git commit -m "feat(wcag): filtr oznacz_jezyk dla atrybutu lang (3.1.2)"
```

---

### Task 2: Allowlista sanityzatora — `span` z `lang`

Bez tego kroku Task 4 cicho nie zadziała: nh3 zredukuje
`<span lang="en">Tytuł</span>` do gołego `Tytuł`.

**Files:**
- Modify: `src/bpp/util/text.py:306-313`
- Test: `src/bpp/tests/test_util/test_sanityzator_span_lang.py`

**Interfaces:**
- Consumes: nic
- Produces: `safe_opis_bibliograficzny_html()` przepuszcza `<span lang="…">`;
  wszystkie pozostałe atrybuty `span` nadal wycinane. Wymagane przez Task 4.

- [ ] **Step 1: Napisz test regresji bezpieczeństwa**

Utwórz `src/bpp/tests/test_util/test_sanityzator_span_lang.py`:

```python
"""Allowlista sanityzatora opisu bibliograficznego po dopuszczeniu ``span``.

Opis powstaje z (niezaufanego) tytułu i jest renderowany ``|safe`` na
publicznych stronach, więc rozszerzenie allowlisty musi być wąskie:
``lang`` jest deklaratywny (nie wykonuje kodu, nie ładuje zasobów), ale
``style``/``class``/``on*`` na ``span`` nadal muszą wylatywać.
"""

from bpp.util import safe_opis_bibliograficzny_html


def test_span_z_lang_przechodzi():
    wynik = safe_opis_bibliograficzny_html('<span lang="en">Effects</span>')
    assert wynik == '<span lang="en">Effects</span>'


def test_span_z_kodem_regionalnym_przechodzi():
    wynik = safe_opis_bibliograficzny_html('<span lang="en-GB">Colour</span>')
    assert 'lang="en-GB"' in wynik


def test_span_zachowuje_zagniezdzona_kursywe():
    wynik = safe_opis_bibliograficzny_html(
        '<span lang="en">Role of <i>Candida</i></span>'
    )
    assert "<i>Candida</i>" in wynik
    assert 'lang="en"' in wynik


def test_span_traci_atrybut_style():
    wynik = safe_opis_bibliograficzny_html(
        '<span style="position:fixed;top:0">X</span>'
    )
    assert "style" not in wynik
    assert "<span>X</span>" in wynik


def test_span_traci_atrybut_class():
    wynik = safe_opis_bibliograficzny_html('<span class="evil">X</span>')
    assert "class" not in wynik


def test_span_traci_atrybut_zdarzenia():
    wynik = safe_opis_bibliograficzny_html(
        '<span onmouseover="alert(1)" lang="en">X</span>'
    )
    assert "onmouseover" not in wynik
    assert "alert" not in wynik
    assert 'lang="en"' in wynik


def test_script_nadal_usuwany_wraz_z_trescia():
    wynik = safe_opis_bibliograficzny_html(
        '<span lang="en">Tytuł</span><script>alert(1)</script>'
    )
    assert "<script" not in wynik
    assert "alert(1)" not in wynik


def test_link_autora_nadal_dziala():
    # Regresja: rozszerzenie allowlisty nie może zepsuć wariantu z linkami.
    wynik = safe_opis_bibliograficzny_html(
        '<a href="/bpp/autor/1/">Kowalski Jan</a>'
    )
    assert 'href="/bpp/autor/1/"' in wynik


def test_tag_spoza_allowlisty_nadal_usuwany():
    wynik = safe_opis_bibliograficzny_html("<div>blok</div>")
    assert "<div>" not in wynik
    assert "blok" in wynik
```

- [ ] **Step 2: Uruchom test — musi paść**

```bash
uv run pytest src/bpp/tests/test_util/test_sanityzator_span_lang.py -v
```

Oczekiwane: FAIL na `test_span_z_lang_przechodzi` — wynik to `Effects`
(znacznik wycięty). Testy negatywne (`style`, `class`, `onmouseover`) mogą
przechodzić już teraz, bo dziś cały `span` jest usuwany.

- [ ] **Step 3: Rozszerz allowlistę**

W `src/bpp/util/text.py`, klasa `safe_opis_bibliograficzny_defaults`
(linie 306-313), zamień:

```python
class safe_opis_bibliograficzny_defaults:
    # Opis bibliograficzny składa się z tytułu (sanityzowanego jak wyżej) oraz
    # inline'owego formatowania cytowania; w wariancie linkowanym niesie też
    # odnośniki autorów (``<a href>``). Dopuszczamy TE SAME tagi co tytuł plus
    # ``<a>`` z samym ``href``/``rel``/``title`` — bez tagów blokowych, bez
    # ``style``/``class`` i bez innych atrybutów.
    ALLOWED_TAGS = safe_tytul_defaults.ALLOWED_TAGS + ("a",)
    ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}
```

na:

```python
class safe_opis_bibliograficzny_defaults:
    # Opis bibliograficzny składa się z tytułu (sanityzowanego jak wyżej) oraz
    # inline'owego formatowania cytowania; w wariancie linkowanym niesie też
    # odnośniki autorów (``<a href>``). Dopuszczamy TE SAME tagi co tytuł plus
    # ``<a>`` z samym ``href``/``rel``/``title`` oraz ``<span>`` WYŁĄCZNIE
    # z ``lang`` — bez tagów blokowych, bez ``style``/``class``.
    #
    # ``span``/``lang`` są tu dla WCAG 3.1.2 (Language of Parts): generator
    # opisu owija tytuł obcojęzyczny znacznikiem języka, a bez tego wpisu nh3
    # wyciąłby go i poprawka cicho by nie działała. ``lang`` jest atrybutem
    # deklaratywnym — nie wykonuje kodu, nie ładuje zasobów, nie wpływa na
    # układ; ``span`` bez ``style``/``class`` nie pozwala nadpisać wyglądu.
    ALLOWED_TAGS = safe_tytul_defaults.ALLOWED_TAGS + ("a", "span")
    ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"], "span": ["lang"]}
```

- [ ] **Step 4: Uruchom test — musi przejść**

```bash
uv run pytest src/bpp/tests/test_util/test_sanityzator_span_lang.py -v
```

Oczekiwane: 9 passed.

- [ ] **Step 5: Uruchom istniejące testy sanityzacji (regresja)**

```bash
uv run pytest src/bpp/tests/test_util/ -v
uv run pytest src/bpp/tests/ -k "sanity or safe_tytul or safe_opis" -v
```

Oczekiwane: wszystkie przechodzą — rozszerzenie jest addytywne.

- [ ] **Step 6: Commit**

```bash
uv run ruff format src/bpp/util/text.py \
    src/bpp/tests/test_util/test_sanityzator_span_lang.py
uv run ruff check src/bpp/util/text.py \
    src/bpp/tests/test_util/test_sanityzator_span_lang.py
git add src/bpp/util/text.py \
    src/bpp/tests/test_util/test_sanityzator_span_lang.py
git commit -m "feat(wcag): dopusc span[lang] w sanityzatorze opisu (3.1.2)"
```

---

### Task 3: Wektor 1 — `lang` na stronach szczegółów

Dwa żywe szablony renderujące tytuł z pól modelu. Efekt natychmiast po
wdrożeniu, bez czekania na przeliczenie cache.

**Files:**
- Modify: `src/bpp/templates/browse/praca_tabela_mono.html:16-22`
- Modify: `src/bpp/templates/browse/praca.html:48-50`
- Create: `src/bpp/tests/test_wcag/__init__.py`
- Test: `src/bpp/tests/test_wcag/test_lang_szablony.py`

**Interfaces:**
- Consumes: filtr `oznacz_jezyk` z Task 1
- Produces: nic dla dalszych zadań

- [ ] **Step 1: Utwórz pakiet testów**

```bash
mkdir -p src/bpp/tests/test_wcag
touch src/bpp/tests/test_wcag/__init__.py
```

- [ ] **Step 2: Napisz testy szablonów**

Utwórz `src/bpp/tests/test_wcag/test_lang_szablony.py`:

```python
"""WCAG 3.1.2 — atrybut ``lang`` na tytułach na stronach szczegółów.

Tytuł oryginalny bierze język z ``rekord.jezyk``. Tytuł PRZEŁOŻONY
(``tytul``) świadomie NIE dostaje atrybutu: model nie zawiera pola
opisującego jego język (``jezyk_alt`` to odwzorowanie atrybutu z API PBN
oznaczające drugi język PRACY, nie język przekładu). Bez atrybutu przekład
dziedziczy ``lang="pl"`` ze strony, co dla polskiego tłumaczenia jest
prawdą — a błędne oznaczenie byłoby gorsze niż brak.
"""

import pytest
from django.template.loader import render_to_string
from model_bakery import baker

from bpp.models.system import Jezyk

# Fixture ``jezyki`` (src/fixtures/conftest_system.py:65) tworzy słownik
# z WYPEŁNIONYM ``kod_bcp47``: polski → "pl", angielski → "en". Fixture
# ``wydawnictwo_ciagle`` już od niej zależy, więc wystarczy pobrać język
# po skrócie zamiast budować własny.


@pytest.fixture
def jezyk_angielski(jezyki):
    return Jezyk.objects.get(skrot="ang.")


@pytest.fixture
def jezyk_bez_kodu(db):
    return baker.make(Jezyk, nazwa="suahili", skrot="swa.", kod_bcp47="")


def _renderuj_mono(praca):
    return render_to_string(
        "browse/praca_tabela_mono.html",
        {"praca": praca, "autorzy": [], "rekord": praca, "links": "normal"},
    )


@pytest.mark.django_db
def test_mono_oznacza_tytul_oryginalny(wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    tresc = _renderuj_mono(wydawnictwo_ciagle)

    assert 'lang="en"' in tresc


@pytest.mark.django_db
def test_mono_bez_atrybutu_gdy_kod_pusty(wydawnictwo_ciagle, jezyk_bez_kodu):
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł bez kodu"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_bez_kodu
    wydawnictwo_ciagle.save()

    tresc = _renderuj_mono(wydawnictwo_ciagle)

    assert "Tytuł bez kodu" in tresc
    assert 'lang=""' not in tresc


@pytest.mark.django_db
def test_mono_przeklad_zostaje_poza_znacznikiem(
    wydawnictwo_ciagle, jezyk_angielski
):
    # Znacznik obejmuje WYŁĄCZNIE tytuł oryginalny. Wspólny <span> na bloku
    # "oryginalny (przekład)" oznaczyłby jednym językiem dwa różne języki.
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X"
    wydawnictwo_ciagle.tytul = "Wpływ X"
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    tresc = _renderuj_mono(wydawnictwo_ciagle)

    assert '<span lang="en">Effects of X</span>' in tresc
    assert "Wpływ X" in tresc
    assert '<span lang="en">Effects of X (Wpływ X)' not in tresc


@pytest.mark.django_db
def test_breadcrumb_oznacza_tytul(client, wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    res = client.get(wydawnictwo_ciagle.get_absolute_url())

    assert res.status_code == 200
    assert b'lang="en"' in res.content


@pytest.mark.django_db
def test_breadcrumb_bez_atrybutu_gdy_kod_pusty(
    client, wydawnictwo_ciagle, jezyk_bez_kodu
):
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł bez kodu"
    wydawnictwo_ciagle.jezyk = jezyk_bez_kodu
    wydawnictwo_ciagle.save()

    res = client.get(wydawnictwo_ciagle.get_absolute_url())

    assert res.status_code == 200
    assert b'lang=""' not in res.content
```

- [ ] **Step 3: Uruchom testy — muszą paść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_lang_szablony.py -v
```

Oczekiwane: FAIL — brak `lang="en"` w wyrenderowanej treści.

Fixture `wydawnictwo_ciagle` jest zarejestrowana globalnie przez
`pytest_plugins` w `src/conftest.py:47` (moduł
`src/fixtures/conftest_publications.py:87`) — działa w każdym pakiecie
testowym bez importu. `get_absolute_url` pochodzi z
`ModelZAbsolutnymUrl` (`src/bpp/models/abstract/web.py:45`) i zwraca URL po
slugu albo po `(content_type, pk)`.

- [ ] **Step 4: Zmień `praca_tabela_mono.html`**

Linie 16-22, blok `<h2 class="praca-mono__title">`. Zamień:

```django
            {% if praca.tytul %}
                {{ praca.tytul_oryginalny|safe_tytul }}
                <span class="praca-mono__title-translation">({{ praca.tytul|safe_tytul }})</span>
            {% else %}
                {{ praca.tytul_oryginalny|znak_na_koncu:"."|safe_tytul }}
            {% endif %}
```

na:

```django
            {# WCAG 3.1.2: znacznik jezyka TYLKO na tytule oryginalnym. #}
            {# Przeklad nie ma w modelu pola z jezykiem, wiec dziedziczy #}
            {# lang="pl" ze strony — patrz spec 2026-08-06. #}
            {% if praca.tytul %}
                {{ praca.tytul_oryginalny|safe_tytul|oznacz_jezyk:praca.jezyk }}
                <span class="praca-mono__title-translation">({{ praca.tytul|safe_tytul }})</span>
            {% else %}
                {{ praca.tytul_oryginalny|znak_na_koncu:"."|safe_tytul|oznacz_jezyk:praca.jezyk }}
            {% endif %}
```

Biblioteka `prace` jest już załadowana w linii 1 — nie zmieniaj `{% load %}`.

- [ ] **Step 5: Zmień breadcrumb w `praca.html`**

Linia 49. Zamień:

```django
    <li class="current">{{ rekord.tytul_oryginalny|truncatewords_html:15|safe_tytul }}</li>
```

na:

```django
    {# WCAG 3.1.2 — jezyk tytulu oryginalnego w okruszku nawigacyjnym. #}
    <li class="current">{{ rekord.tytul_oryginalny|truncatewords_html:15|safe_tytul|oznacz_jezyk:rekord.jezyk }}</li>
```

`praca.html` zaczyna się od `{% extends "base.html" %}` i **nie ma**
`{% load prace %}`. Dopisz go w drugiej linii pliku:

```django
{% extends "base.html" %}
{% load prace %}
```

Jeżeli plik ma już inny `{% load %}` tuż po `extends`, dopisz `prace` do
tej listy zamiast dodawać nową linię.

`rekord` to `Rekord` (materializacja) — dziedziczy `ModelTypowany`, więc ma
`jezyk`. Pola `jezyk_alt`/`jezyk_orig` są tam ustawione na `None`
(`src/bpp/models/cache/rekord.py:262-263`), ale ich nie używamy.

- [ ] **Step 6: Uruchom testy — muszą przejść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_lang_szablony.py -v
```

Oczekiwane: 3 passed.

- [ ] **Step 7: Regresja widoków browse**

```bash
uv run pytest src/bpp/tests/test_views/test_browse -v
```

Oczekiwane: bez nowych błędów.

- [ ] **Step 8: Commit**

```bash
git add src/bpp/templates/browse/praca_tabela_mono.html \
    src/bpp/templates/browse/praca.html \
    src/bpp/tests/test_wcag/
git commit -m "feat(wcag): lang na tytulach stron szczegolow (3.1.2 wektor 1)"
```

---

### Task 4: Wektor 2 — `lang` w generatorze opisu

Dwa szablony będące wariantami generatora opisu bibliograficznego. Efekt na
listach i w wynikach wyszukiwania pojawia się po nocnym `denorm_rebuild`.

**Files:**
- Modify: `src/bpp/templates/opis_bibliograficzny.html:7-11`
- Modify: `src/bpp/templates/browse/praca_tabela.html:7-11`
- Test: `src/bpp/tests/test_wcag/test_lang_opis.py`

**Interfaces:**
- Consumes: filtr `oznacz_jezyk` (Task 1), allowlista `span[lang]` (Task 2)
- Produces: `opis_bibliograficzny_cache` zawiera `<span lang="…">` wokół
  tytułu oryginalnego. Wykorzystane w teście szablonowym Task 5.

- [ ] **Step 1: Napisz testy generatora**

Utwórz `src/bpp/tests/test_wcag/test_lang_opis.py`:

```python
"""WCAG 3.1.2 w opisie bibliograficznym (wektor 2).

Opis jest generowany serwerowo i cache'owany jako gotowy HTML, więc
znacznik języka musi trafić DO ŚRODKA tego HTML-u — poprawka na poziomie
szablonu strony go nie obejmuje.

Asercje idą na wynik ``opis_bibliograficzny()``, a NIE na render samego
szablonu: metoda kończy się sanityzacją nh3, która wycięłaby ``<span>``
gdyby allowlista nie została rozszerzona. Test broni tego rozszerzenia
przed cofnięciem.
"""

import pytest
from model_bakery import baker

from bpp.models.system import Jezyk
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)


@pytest.fixture
def jezyk_angielski(jezyki):
    return Jezyk.objects.get(skrot="ang.")


@pytest.fixture
def jezyk_bez_kodu(db):
    return baker.make(Jezyk, nazwa="suahili", skrot="swa.", kod_bcp47="")


@pytest.mark.django_db
def test_opis_zawiera_lang_tytulu(wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert '<span lang="en">' in opis
    assert "Effects of X on Y" in opis


@pytest.mark.django_db
def test_opis_bez_lang_gdy_kod_pusty(wydawnictwo_ciagle, jezyk_bez_kodu):
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł bez kodu"
    wydawnictwo_ciagle.jezyk = jezyk_bez_kodu
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert "Tytuł bez kodu" in opis
    assert "lang=" not in opis


@pytest.mark.django_db
def test_opis_nie_oznacza_przekladu(wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X"
    wydawnictwo_ciagle.tytul = "Wpływ X"
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert opis.count('lang="en"') == 1
    assert "Wpływ X" in opis


@pytest.mark.django_db
def test_znacznik_przezywa_post_processing(wydawnictwo_ciagle, jezyk_angielski):
    # opis_bibliograficzny() normalizuje interpunkcję łańcuchem .replace()
    # (" , ", " . ", ". . ", " .", ".</b>[" — util.py:106-121). Tytuł
    # kończący się kropką sąsiaduje ze znacznikiem, więc to najbliższy
    # kontakt tych wzorców z <span>.
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X."
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert '<span lang="en">' in opis
    assert "</span>" in opis
    assert "<span lang=" not in opis.replace('<span lang="en">', "")


@pytest.mark.django_db
def test_znacznik_w_wariancie_praca_tabela(wydawnictwo_ciagle, jezyk_angielski):
    # Drugi szablon opisu, instalowany kiedyś przez migrację 0295 obok
    # domyślnego. Leży w katalogu browse/, ale NIE jest stroną — żaden widok
    # go nie renderuje; wchodzi wyłącznie przez nazwa_szablonu.
    SzablonDlaOpisuBibliograficznego.objects.update_or_create(
        model=None,
        defaults={"nazwa_szablonu": "browse/praca_tabela.html"},
    )
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert '<span lang="en">' in opis


@pytest.mark.django_db
def test_kursywa_w_tytule_przezywa_obok_znacznika(
    wydawnictwo_ciagle, jezyk_angielski
):
    wydawnictwo_ciagle.tytul_oryginalny = "Role of <i>Candida</i> in X"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert "<i>Candida</i>" in opis
    assert 'lang="en"' in opis
```

- [ ] **Step 2: Uruchom testy — muszą paść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_lang_opis.py -v
```

Oczekiwane: FAIL — brak `<span lang="en">` w opisie.

- [ ] **Step 3: Zmień `opis_bibliograficzny.html`**

Linie 7-11. Zamień:

```django
{% if praca.tytul %}
    <b>{{ praca.tytul_oryginalny|safe }} ({{ praca.tytul|safe }}).</b>
{% else %}
    <b>{{ praca.tytul_oryginalny|znak_na_koncu:"."|safe }}</b>
{% endif %}
```

na:

```django
{# WCAG 3.1.2: znacznik jezyka TYLKO na tytule oryginalnym. Musi byc #}
{# w srodku cache'owanego HTML-u, bo listy i wyniki wyszukiwania #}
{# wstawiaja gotowy blob, nie renderuja pol modelu. #}
{% if praca.tytul %}
    <b>{{ praca.tytul_oryginalny|safe|oznacz_jezyk:praca.jezyk }} ({{ praca.tytul|safe }}).</b>
{% else %}
    <b>{{ praca.tytul_oryginalny|znak_na_koncu:"."|safe|oznacz_jezyk:praca.jezyk }}</b>
{% endif %}
```

`{% load prace %}` jest już w linii 1.

- [ ] **Step 4: Zmień `browse/praca_tabela.html`**

Linie 7-11. Zamień:

```django
            {% if praca.tytul %}
                <b>{{ praca.tytul_oryginalny|safe }} ({{ praca.tytul|safe }}).</b>
            {% else %}
                <b>{{ praca.tytul_oryginalny|znak_na_koncu:"."|safe }}</b>
            {% endif %}
```

na:

```django
            {# WCAG 3.1.2 — jak w opis_bibliograficzny.html. Ten plik to #}
            {# WARIANT generatora opisu (migracja 0295), nie strona: #}
            {# praca.html wlacza wylacznie praca_tabela_mono.html. #}
            {% if praca.tytul %}
                <b>{{ praca.tytul_oryginalny|safe|oznacz_jezyk:praca.jezyk }} ({{ praca.tytul|safe }}).</b>
            {% else %}
                <b>{{ praca.tytul_oryginalny|znak_na_koncu:"."|safe|oznacz_jezyk:praca.jezyk }}</b>
            {% endif %}
```

`{% load prace %}` jest już w linii 1.

- [ ] **Step 5: Uruchom testy — muszą przejść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_lang_opis.py -v
```

Oczekiwane: 6 passed.

- [ ] **Step 6: Regresja opisu bibliograficznego**

```bash
uv run pytest src/bpp/tests/ -k "opis_bibliograficzny" -v
uv run pytest src/bpp/tests/test_models/ -v
```

Oczekiwane: bez nowych błędów. Testy asertujące dokładną treść opisu mogą
wymagać aktualizacji o `<span lang="…">` — to zmiana oczekiwana, nie
regresja; popraw asercje.

- [ ] **Step 7: Commit**

```bash
git add src/bpp/templates/opis_bibliograficzny.html \
    src/bpp/templates/browse/praca_tabela.html \
    src/bpp/tests/test_wcag/test_lang_opis.py
git commit -m "feat(wcag): lang w generatorze opisu bibliograficznego (3.1.2 wektor 2)"
```

---

### Task 5: Naprawa podświetlania w rekordach powiązanych

Znacznik z Task 4 trafia do `data-records` na publicznej stronie szczegółów.
Wyszukiwarka podświetla trafienia regexem na surowym HTML-u, więc wpisanie
`en` wstawia `<mark>` w środek `lang="en"` i psuje markup.

**Files:**
- Create: `src/bpp/static/bpp/js/related-records-highlight.js`
- Create: `tests/js/related-records-highlight.test.js`
- Modify: `src/bpp/templates/browse/praca_tabela_mono.html` (podpięcie
  modułu, podmiana ciała `rebuildList`)

**Interfaces:**
- Consumes: opis ze znacznikiem (Task 4)
- Produces: globalna funkcja `window.bppHighlightOutsideTags(html, term)`

- [ ] **Step 1: Napisz testy vitest**

Utwórz `tests/js/related-records-highlight.test.js`:

```javascript
// Podswietlanie frazy w opisie bibliograficznym (HTML) — wylacznie w
// segmentach TEKSTOWYCH. Po dodaniu <span lang="en"> (WCAG 3.1.2) naiwny
// regex na calym stringu podswietlal fragmenty ATRYBUTOW: fraza "en"
// trafiala w lang="en" i wstawiala <mark> w srodek znacznika, co przy
// .html(text) daje zepsuty markup.

import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

let highlight;

beforeAll(() => {
    const zrodlo = readFileSync(
        resolve(
            __dirname,
            "../../src/bpp/static/bpp/js/related-records-highlight.js"
        ),
        "utf-8"
    );
    const window = {};
    new Function("window", zrodlo)(window);
    highlight = window.bppHighlightOutsideTags;
});

describe("bppHighlightOutsideTags", () => {
    it("podswietla fraze w tekscie", () => {
        expect(highlight("Effects of X", "effects")).toBe(
            '<mark class="bpp-highlight">Effects</mark> of X'
        );
    });

    it("NIE podswietla frazy wystepujacej tylko w atrybucie", () => {
        const html = '<span lang="en">Wpływ X</span>';
        expect(highlight(html, "en")).toBe(html);
    });

    it("NIE podswietla nazwy atrybutu", () => {
        const html = '<span lang="pl">Tytuł</span>';
        expect(highlight(html, "lang")).toBe(html);
    });

    it("NIE podswietla nazwy znacznika", () => {
        const html = '<span lang="pl">Tytuł</span>';
        expect(highlight(html, "span")).toBe(html);
    });

    it("podswietla w tresci mimo wystapienia w atrybucie", () => {
        const wynik = highlight('<span lang="en">Energy</span>', "en");
        expect(wynik).toBe(
            '<span lang="en"><mark class="bpp-highlight">En</mark>ergy</span>'
        );
    });

    it("nie podswietla frazy rozdzielonej znacznikiem", () => {
        const html = "Rola <i>Candida</i> w X";
        expect(highlight(html, "rola candida")).toBe(html);
    });

    it("traktuje znaki specjalne regexa doslownie", () => {
        expect(highlight("Wpływ (X) na Y", "(x)")).toBe(
            'Wpływ <mark class="bpp-highlight">(X)</mark> na Y'
        );
    });

    it("podswietla wszystkie wystapienia w tresci", () => {
        const wynik = highlight("Ala ma kota, ala ma psa", "ala");
        expect(wynik.match(/<mark/g)).toHaveLength(2);
    });

    it("zachowuje wielkosc liter oryginalu", () => {
        expect(highlight("Effects", "EFFECTS")).toContain(">Effects<");
    });

    it("zwraca wejscie bez zmian dla pustej frazy", () => {
        const html = '<span lang="en">X</span>';
        expect(highlight(html, "")).toBe(html);
    });

    it("nie psuje encji HTML w tresci", () => {
        const html = "Kowalski &amp; Nowak";
        expect(highlight(html, "nowak")).toBe(
            'Kowalski &amp; <mark class="bpp-highlight">Nowak</mark>'
        );
    });
});
```

- [ ] **Step 2: Uruchom testy — muszą paść**

```bash
npx vitest run tests/js/related-records-highlight.test.js
```

Oczekiwane: FAIL — brak pliku `related-records-highlight.js`.

- [ ] **Step 3: Napisz moduł**

Utwórz `src/bpp/static/bpp/js/related-records-highlight.js`:

```javascript
/**
 * Podswietlanie frazy w opisie bibliograficznym (HTML).
 *
 * Opis niesie zamierzony markup (<b>, <i>, <sub>) oraz — od czasu wdrozenia
 * WCAG 3.1.2 — <span lang="xx"> wokol tytulu obcojezycznego. Naiwne
 * `text.replace(regex, '<mark>$1</mark>')` nie odroznia tresci od
 * znacznikow: fraza "en" trafiala w lang="en" i wstawiala <mark> w SRODEK
 * atrybutu, produkujac zepsuty markup przy .html(text).
 *
 * Rozwiazanie: podziel wejscie na segmenty <tag> / tekst i podswietlaj
 * wylacznie w tekstowych.
 */
(function (window) {
    "use strict";

    var TAG_LUB_TEKST = /(<[^>]*>)|([^<]+)/g;

    function escapeRegExp(ciag) {
        return ciag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }

    /**
     * @param {string} html - opis bibliograficzny (moze zawierac znaczniki)
     * @param {string} fraza - szukany tekst (bez rozrozniania wielkosci liter)
     * @returns {string} HTML z <mark> wokol trafien w tresci
     */
    function bppHighlightOutsideTags(html, fraza) {
        if (!fraza) {
            return html;
        }

        var regex = new RegExp("(" + escapeRegExp(fraza) + ")", "gi");

        return html.replace(TAG_LUB_TEKST, function (_, znacznik, tekst) {
            if (znacznik) {
                return znacznik;
            }
            return tekst.replace(regex, '<mark class="bpp-highlight">$1</mark>');
        });
    }

    window.bppHighlightOutsideTags = bppHighlightOutsideTags;
})(typeof window !== "undefined" ? window : this);
```

- [ ] **Step 4: Uruchom testy — muszą przejść**

```bash
npx vitest run tests/js/related-records-highlight.test.js
```

Oczekiwane: 11 passed.

- [ ] **Step 5: Podepnij moduł w szablonie**

Szablon jest fragmentem włączanym przez `{% include %}` — nie ma bloków
`extra_js` ani żadnego `<script src=…>`. Cały jego JS to jeden inline'owy
blok otwierany w linii 974 (`<script type="text/javascript">`).

Dopisz `static` do `{% load %}` w linii 1:

```django
{% load prace user_in_group dspace_links static %}
```

i wstaw znacznik **bezpośrednio przed** linią 974, czyli przed otwarciem
inline'owego bloku:

```django
{# Modul podswietlania — wydzielony z inline'owego JS ponizej, zeby dalo #}
{# sie go przetestowac jednostkowo (tests/js/). #}
<script src="{% static 'bpp/js/related-records-highlight.js' %}"></script>
<script type="text/javascript">
```

Kolejność ma znaczenie: inline'owy blok woła `window.bppHighlightOutsideTags`
dopiero w handlerze `input`, ale ładowanie modułu wcześniej usuwa zależność
od czasu wykonania.

- [ ] **Step 6: Podmień podświetlanie w inline'owym JS**

W tym samym pliku, funkcja `rebuildList` (ok. linii 1178-1199). Zamień:

```javascript
                        // Add simple highlighting if search term provided
                        if (searchTerm) {
                            var escapedTerm = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                            var regex = new RegExp('(' + escapedTerm + ')', 'gi');
                            text = text.replace(regex, '<mark style="background-color: #fff59d; padding: 2px;">$1</mark>');
                        }
```

na:

```javascript
                        // Podswietlanie omijajace znaczniki HTML — opis
                        // niesie <b>/<i> oraz <span lang> (WCAG 3.1.2),
                        // a regex na calym stringu wstawialby <mark>
                        // w srodek atrybutu. Modul: related-records-highlight.js
                        if (searchTerm) {
                            text = window.bppHighlightOutsideTags(text, searchTerm);
                        }
```

- [ ] **Step 7: Dodaj styl `.bpp-highlight`**

Kolor przeniesiony z usuniętego atrybutu `style`. Dopisz na końcu
`src/bpp/static/scss/praca_detail.scss` (obok istniejących
`.praca-mono__related-*`, linie 1001-1030):

```scss
// Podswietlenie trafienia w wyszukiwarce rekordow powiazanych. Kolor
// przeniesiony z inline'owego style="" — modul JS wstawia sam znacznik
// <mark class="bpp-highlight">, bez atrybutow prezentacyjnych.
.bpp-highlight {
    background-color: #fff59d;
    padding: 2px;
}
```

Następnie przebuduj CSS:

```bash
grunt build
```

**Nie nadpisuj klas siatki Foundation** (`medium-4`, `large-12` itp.) —
`.bpp-highlight` jest własną klasą, więc konflikt nie zachodzi.

- [ ] **Step 8: Test szablonowy — znacznik trafia do `data-records`**

Dopisz do `src/bpp/tests/test_wcag/test_lang_opis.py`:

```python
@pytest.mark.django_db
def test_data_records_zawiera_znacznik_jezyka(
    client, wydawnictwo_zwarte, jezyk_angielski, denorms
):
    # Wyszukiwarka rekordów powiązanych czyta surowy HTML opisu z atrybutu
    # data-records (praca_tabela_mono.html:676). Rozdział w wydawnictwie
    # nadrzędnym trafia tam przez wydawnictwa_powiazane_posortowane
    # (wydawnictwo_zwarte.py:263), więc po zmianie generatora niesie
    # <span lang=…> — i to on psuł podświetlanie przed naprawą z Task 5.
    from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

    rozdzial = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Effects of X on Y",
        tytul="",
        jezyk=jezyk_angielski,
        wydawnictwo_nadrzedne=wydawnictwo_zwarte,
        rok=wydawnictwo_zwarte.rok,
    )
    rozdzial.opis_bibliograficzny_cache = rozdzial.opis_bibliograficzny()
    rozdzial.save()

    res = client.get(wydawnictwo_zwarte.get_absolute_url())

    assert res.status_code == 200
    assert b"data-records" in res.content
    assert b"lang=" in res.content
```

`opis_bibliograficzny_cache` jest polem `@denormalized`, przeliczanym
asynchronicznie przez kolejkę `denorm`. W teście przypisujemy je wprost
(`rozdzial.opis_bibliograficzny() → save()`), żeby nie zależeć od flushu.

Fixture `denorms` jest zdefiniowana w `src/fixtures/conftest_system.py:255`
i zarejestrowana globalnie przez `pytest_plugins`.

- [ ] **Step 9: Uruchom testy JS i Pythona**

```bash
make js-tests
uv run pytest src/bpp/tests/test_wcag/ -v
```

Oczekiwane: wszystkie przechodzą.

- [ ] **Step 10: Commit**

```bash
git add src/bpp/static/bpp/js/related-records-highlight.js \
    tests/js/related-records-highlight.test.js \
    src/bpp/templates/browse/praca_tabela_mono.html \
    src/bpp/static/scss/ \
    src/bpp/tests/test_wcag/test_lang_opis.py
git commit -m "fix(wcag): podswietlanie omija znaczniki HTML w rekordach powiazanych"
```

---

### Task 6: Testy substring-search w kolejce PBN

Trzy miejsca szukają frazy w surowym `opis_bibliograficzny_cache`. Kodu nie
zmieniamy — dokumentujemy, że znacznik ich nie psuje.

**Files:**
- Test: `src/pbn_export_queue/tests/test_wyszukiwanie_opisu.py`

**Interfaces:**
- Consumes: opis ze znacznikiem (Task 4)
- Produces: nic

- [ ] **Step 1: Napisz testy**

Utwórz `src/pbn_export_queue/tests/test_wyszukiwanie_opisu.py`:

```python
"""Wyszukiwanie po podłańcuchu w ``opis_bibliograficzny_cache``.

Trzy miejsca w kolejce PBN filtrują rekordy przez ``fraza in opis.lower()``
na SUROWYM HTML-u. Po dodaniu ``<span lang="…">`` (WCAG 3.1.2) sprawdzamy,
że fraza niesąsiadująca ze znacznikiem nadal znajduje rekord.

UWAGA na kształt gałęzi: w ``list_views`` i ``action_views`` opis jest
sprawdzany w ``elif`` — wyłącznie gdy rekord NIE ma ``tytul_oryginalny``.
Test tworzący rekord z tytułem nigdy w tę gałąź nie trafi i przechodziłby
fałszywie.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from pbn_export_queue.views.utils import _get_record_title

OPIS_ZE_ZNACZNIKIEM = (
    'Kowalski Jan. <span lang="en">Effects of X on Y</span>. '
    "Postępy Higieny 2024, t. 78, s. 112-119."
)


def test_get_record_title_zwraca_opis_ze_znacznikiem(wydawnictwo_ciagle):
    wydawnictwo_ciagle.tytul_oryginalny = ""
    wydawnictwo_ciagle.opis_bibliograficzny_cache = OPIS_ZE_ZNACZNIKIEM

    assert _get_record_title(wydawnictwo_ciagle) == OPIS_ZE_ZNACZNIKIEM


def test_get_record_title_woli_tytul_nad_opisem(wydawnictwo_ciagle):
    # Gałąź elif: opis czytany WYŁĄCZNIE gdy brak tytułu oryginalnego.
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł wprost"
    wydawnictwo_ciagle.opis_bibliograficzny_cache = OPIS_ZE_ZNACZNIKIEM

    assert _get_record_title(wydawnictwo_ciagle) == "Tytuł wprost"


@pytest.mark.django_db
def test_lista_kolejki_znajduje_rekord_po_opisie(admin_client, wydawnictwo_ciagle):
    # Realny filtr widoku (list_views.py:76-83) na rekordzie BEZ tytułu
    # oryginalnego — inaczej dopasowanie nigdy nie sięgnie opisu.
    from pbn_export_queue.models import PBN_Export_Queue

    wydawnictwo_ciagle.tytul_oryginalny = ""
    wydawnictwo_ciagle.opis_bibliograficzny_cache = OPIS_ZE_ZNACZNIKIEM
    wydawnictwo_ciagle.save()

    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=None,
    )

    res = admin_client.get(
        reverse("pbn_export_queue:list"), {"search": "postępy higieny"}
    )

    assert res.status_code == 200
```

Drugi test zależy od nazwy URL-a i pola formularza wyszukiwania. Sprawdź je
przed napisaniem testu:

```bash
grep -rn "name=\"list\"\|name='list'" src/pbn_export_queue/urls.py
grep -n "search" src/pbn_export_queue/views/list_views.py | head -5
```

Dostosuj `reverse(...)`, nazwę parametru GET oraz pole
`rekord_do_wysylki`/`zamowil` do rzeczywistego modelu
(`src/pbn_export_queue/models.py`). Jeżeli widok wymaga uprawnień innych niż
`admin_client`, użyj właściwej fixture — ale **nie** zamieniaj tego testu na
asercję o samej stałej `OPIS_ZE_ZNACZNIKIEM`: test ma wykonywać kod
produkcyjny, inaczej nie testuje niczego.

- [ ] **Step 2: Uruchom testy**

```bash
uv run pytest src/pbn_export_queue/tests/test_wyszukiwanie_opisu.py -v
```

Oczekiwane: 3 passed.

`_get_record_title(rekord)` (`src/pbn_export_queue/views/utils.py:188-202`)
sprawdza `tytul_oryginalny`, a opis czyta dopiero w `elif` — dlatego test
zeruje tytuł. Funkcja nie dotyka bazy, więc `@pytest.mark.django_db` nie
jest tu potrzebne; fixture `wydawnictwo_ciagle` dostarcza tylko obiekt
o właściwym kształcie.

- [ ] **Step 3: Commit**

```bash
uv run ruff format src/pbn_export_queue/tests/test_wyszukiwanie_opisu.py
uv run ruff check src/pbn_export_queue/tests/test_wyszukiwanie_opisu.py
git add src/pbn_export_queue/tests/test_wyszukiwanie_opisu.py
git commit -m "test(wcag): wyszukiwanie po opisie ze znacznikiem jezyka"
```

---

### Task 7: 1.1.1 — obrazy bez `alt`

**Files:**
- Modify: `src/bpp/templates/504.html:12-13`
- Delete: `src/bpp/templates/user_navigation_autocomplete.html`
- Test: `src/bpp/tests/test_wcag/test_alt_obrazy.py`

**Interfaces:**
- Consumes: pakiet `src/bpp/tests/test_wcag/` (Task 3, krok 1)
- Produces: nic

- [ ] **Step 1: Napisz test**

Utwórz `src/bpp/tests/test_wcag/test_alt_obrazy.py`:

```python
"""WCAG 1.1.1 — treść nietekstowa.

Ikona obok pełnego komunikatu tekstowego jest DEKORACJĄ, więc właściwą
wartością jest ``alt=""`` (pusty), a nie opis. Pusty ``alt`` każe czytnikowi
element POMINĄĆ; brak atrybutu każe mu odczytać nazwę pliku
("database dot es vee gee").
"""

from pathlib import Path

import lxml.html
from django.template.loader import render_to_string

SZABLONY = Path(__file__).resolve().parents[2] / "templates"


def test_504_ma_pusty_alt_na_ikonie():
    html = render_to_string("504.html")
    obrazy = lxml.html.fromstring(html).xpath("//img")

    assert obrazy, "szablon 504.html powinien zawierać <img>"
    for img in obrazy:
        assert img.get("alt") == "", (
            f"<img src={img.get('src')!r}> musi mieć alt='' (dekoracja)"
        )


def test_martwy_szablon_autocomplete_usuniety():
    # Szablon renderował <img> bez alt, ale nie był używany: widok
    # bpp:navigation-autocomplete zwraca JSON (Select2QuerySetSequenceView),
    # a listę rysuje Select2 po stronie klienta.
    assert not (SZABLONY / "user_navigation_autocomplete.html").exists()


def test_504_deklaruje_jezyk_polski():
    # WCAG 3.1.1 (Language of Page, poziom A). Treść strony jest polska
    # ("Przekroczono dozwolony czas wykonywania zapytania"), a dokument
    # deklarował lang="en" — czytnik odczytywał CAŁĄ stronę angielską
    # fonetyką. Jedyny samodzielny szablon z własnym <html lang=…>;
    # pozostałe dziedziczą po base.html.
    html = render_to_string("504.html")
    korzen = lxml.html.fromstring(html)

    assert korzen.get("lang") == "pl"
```

- [ ] **Step 2: Uruchom testy — muszą paść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_alt_obrazy.py -v
```

Oczekiwane: oba FAIL — brak `alt` i istniejący plik.

`504.html` to samodzielny dokument (`<!DOCTYPE html>`, bez `{% extends %}`
i bez `{% load %}`), więc `render_to_string("504.html")` działa bez
kontekstu.

- [ ] **Step 3: Dodaj `alt=""` w `504.html`**

Linie 12-13. Zamień:

```html
        <img src="/static/bpp/svg/database.svg" style="max-width: 2.8em;"
             align="absmiddle"/>
```

na:

```html
        <img src="/static/bpp/svg/database.svg" style="max-width: 2.8em;"
             align="absmiddle" alt=""/>
```

- [ ] **Step 3b: Popraw deklarację języka w `504.html`**

Linia 2. Zamień:

```html
<html lang="en">
```

na:

```html
<html lang="pl">
```

Treść strony jest polska, więc `lang="en"` kazał czytnikowi odczytać ją
angielską fonetyką — WCAG 3.1.1 (Language of Page, poziom A). To jedyny
samodzielny szablon w projekcie z własnym `<html lang>`; wszystkie inne
dziedziczą po `base.html`.

- [ ] **Step 4: Usuń martwy szablon**

```bash
git rm src/bpp/templates/user_navigation_autocomplete.html
```

- [ ] **Step 5: Uruchom testy — muszą przejść**

```bash
uv run pytest src/bpp/tests/test_wcag/test_alt_obrazy.py -v
```

Oczekiwane: 3 passed.

- [ ] **Step 6: Potwierdź, że nic nie odwoływało się do szablonu**

```bash
grep -rn "user_navigation_autocomplete" src/ templates/ --include="*.py" \
    --include="*.html" --include="*.js"
```

Oczekiwane: brak wyników.

- [ ] **Step 7: Commit**

```bash
git add src/bpp/templates/504.html src/bpp/tests/test_wcag/test_alt_obrazy.py
git commit -m "fix(wcag): alt='' na ikonie 504, usuniecie martwego szablonu (1.1.1)"
```

---

### Task 8: Korekty specyfikacji 08-05, wykaz odroczonych, newsfragmenty

**Files:**
- Modify: `docs/superpowers/specs/2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md`
- Create: `src/bpp/newsfragments/wcag-lang-tytulow.feature.rst`
- Create: `src/bpp/newsfragments/wcag-alt-obrazow.bugfix.rst`

**Interfaces:**
- Consumes: nic
- Produces: nic

- [ ] **Step 1: Dodaj sekcję „Odroczone niezgodności" w specyfikacji 08-05**

Wstaw przed sekcją „Poza zakresem" (koniec pliku). Treść — pięć wpisów,
skopiuj z sekcji o tej samej nazwie w
`docs/superpowers/specs/2026-08-06-wcag-naprawy-stwierdzone-design.md`
(2.1.4, 2.5.7, 3.1.2 dla przekładu, 3.1.2 przy pustym `kod_bcp47`, 3.1.2
przy własnym szablonie opisu, 3.1.2 przy własnym
`OPIS_BIBLIOGRAFICZNY_ALLOWED_TAGS`), dopisując nagłówek:

```markdown
## Odroczone niezgodności

Decyzje podjęte 2026-08-06 przy wykonywaniu kroku 3 („Naprawy stwierdzone").
Zapisane tutaj, bo raport zgodności — właściwe miejsce takich wpisów —
jeszcze nie istnieje. Szczegóły i uzasadnienia:
`2026-08-06-wcag-naprawy-stwierdzone-design.md`.
```

- [ ] **Step 2: Popraw twierdzenie o liveops (sekcja „3.1.2 Language of Parts")**

Znajdź akapit zaczynający się „**Wektor 2 — `opis_bibliograficzny_cache`
(kosztowny).**". Po zdaniu kończącym się „czyli migracji danych na
produkcji." dopisz:

```markdown
**Korekta (2026-08-06):** to ustalenie jest nieprawdziwe. Przeliczenie
całej bazy dzieje się co noc niezależnie od tej zmiany —
`denorm_rebuild --no-flush` o 22:00 z harmonogramu Ofelii
(`bpp-deploy/docker-compose.application.yml:117-118`) brudzi wszystkie
wiersze, kolejka `denorm` je przelicza, a trigger `bpp_refresh_cache`
propaguje wynik do `bpp_rekord_mat`. Rzeczywistym warunkiem koniecznym
wektora 2 jest rozszerzenie allowlisty nh3 o `span`/`lang`
(`src/bpp/util/text.py:306-313`), którego ten dokument nie wymieniał.
Wektor 2 został wykonany 2026-08-06.
```

- [ ] **Step 3: Popraw wpis o martwym szablonie (sekcja „1.1.1 Non-text Content")**

Po zdaniu wymieniającym `user_navigation_autocomplete.html:7` dopisz:

```markdown
**Korekta (2026-08-06):** `user_navigation_autocomplete.html` jest martwy —
żaden widok go nie renderuje. Widok `bpp:navigation-autocomplete` zwraca
JSON (`Select2QuerySetSequenceView`), a listę rysuje Select2 po stronie
klienta. Szablon usunięto zamiast dopisywać `alt`. W zakresie zostaje jeden
obraz, nie dwa.
```

- [ ] **Step 4: Popraw wpis o `praca_tabela.html`, jeśli występuje**

```bash
grep -n "praca_tabela" \
    docs/superpowers/specs/2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md
```

Jeżeli dokument opisuje `browse/praca_tabela.html` jako stronę lub widok,
dopisz w tym miejscu:

```markdown
**Korekta (2026-08-06):** `browse/praca_tabela.html` nie jest stroną —
mimo katalogu `browse/` jest to WARIANT generatora opisu bibliograficznego
(instalowany przez migrację `0295_instaluj_szablony.py:25` obok
`opis_bibliograficzny.html`). Strona szczegółów włącza wyłącznie
`praca_tabela_mono.html` (`browse/praca.html:54`).
```

Jeżeli grep nic nie zwróci, pomiń ten krok.

- [ ] **Step 5: Napisz newsfragmenty**

`src/bpp/newsfragments/wcag-lang-tytulow.feature.rst`:

```rst
Tytuły obcojęzyczne publikacji są teraz oznaczane atrybutem ``lang``
(kryterium WCAG 2.2 AA 3.1.2) — na stronach szczegółów, listach i w wynikach
wyszukiwania. Czytnik ekranu odczyta angielski tytuł angielską fonetyką
zamiast polskiej. Wymaga wypełnionego pola „Kod języka wg BCP 47" w słowniku
języków; opisy bibliograficzne złapią znacznik po najbliższym nocnym
przeliczeniu.
```

`src/bpp/newsfragments/wcag-alt-obrazow.bugfix.rst`:

```rst
Strona przekroczenia czasu zapytania (błąd 504) jest poprawnie odczytywana
przez czytniki ekranu: ikona ma atrybut ``alt`` (nie jest już czytana jako
nazwa pliku graficznego), a dokument deklaruje język polski zamiast
angielskiego — wcześniej cała polska treść była odczytywana angielską
fonetyką (kryteria WCAG 2.2 AA 1.1.1 i 3.1.1).
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md \
    src/bpp/newsfragments/wcag-lang-tytulow.feature.rst \
    src/bpp/newsfragments/wcag-alt-obrazow.bugfix.rst
git commit -m "docs(wcag): korekty spec 08-05, wykaz odroczonych, newsfragmenty"
```

---

### Task 9: Weryfikacja końcowa i PR

- [ ] **Step 1: Pełny przebieg testów bez Playwrighta**

```bash
cd /Volumes/SSD/Programowanie/bpp-wcag-naprawy
make tests-without-playwright
```

Oczekiwane: zielono. Testy asertujące dokładną treść opisu
bibliograficznego mogą wymagać aktualizacji o `<span lang="…">` — popraw
asercje, nie kod produkcyjny.

- [ ] **Step 2: Testy JS**

```bash
make js-tests
```

Oczekiwane: zielono, w tym 11 nowych testów podświetlania.

- [ ] **Step 3: Testy Playwright**

```bash
make assets
make playwright-install
make tests-only-playwright
```

Pierwszy przebieg bywa wolny (zimny start testcontainerów) i `page.goto`
potrafi raz timeoutnąć — ponów.

- [ ] **Step 4: pre-commit**

```bash
pre-commit
```

Problemy naprawiaj **ręcznie**, edytorem, po jednym. Nie uruchamiaj
`ruff check --fix` ani innych automatycznych poprawek zbiorczych.

- [ ] **Step 5: Obejrzyj efekt w przeglądarce**

```bash
uv run run-site run --from-dump ~/db-backup-20260428-093811.pg_dump --no-browser
```

Sprawdź na stronie szczegółów publikacji z angielskim tytułem, że
`<span lang="en">` jest w źródle strony, a wyszukiwarka rekordów powiązanych
z frazą „en" nie psuje układu listy.

- [ ] **Step 6: Push i PR**

```bash
git push -u origin fix-wcag-naprawy-stwierdzone
gh pr create --base dev \
    --title "Naprawy WCAG stwierdzone lekturą kodu (1.1.1, 3.1.2)" \
    --body-file -
```

Treść opisu PR: cel, lista naprawionych kryteriów, informacja o rolloucie
wektora 2 przez nocny `denorm_rebuild`, lista świadomie odroczonych
niezgodności, odniesienie do obu dokumentów w `docs/superpowers/specs/`.

- [ ] **Step 7: Poczekaj na realne gejty CI**

Zielono liczy się dopiero, gdy przejdą **oba**: `Build test-runner image`
oraz **wszystkie** shardy `Tests (sharded)`. Checki kończące się w minutę
(`Docs`, `Lint changed files`, `Check baseline freshness`) nie są dowodem
poprawności.
