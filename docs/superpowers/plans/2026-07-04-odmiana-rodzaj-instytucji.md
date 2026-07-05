# Odmiana instytucji silnikiem SGJP + Rzeczownik jako lemat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zastąpić zakodowaną-na-sztywno tabelę odmiany `jezyk_polski.deklinacja` prawdziwą odmianą przez przypadki (silnik SGJP `django-polish-inflection`), zachowując model `Rzeczownik` jako per-install źródło nazwy odchudzone do jednego pola = mianownik l.poj.

**Architecture:** `Rzeczownik(uid).m` trzyma tylko mianownik (lemat, edytowalny w adminie). Silnik generuje z niego każdy przypadek i liczbę mnogą. Trzy lematy (`UCZELNIA`/`WYDZIAL`/`JEDNOSTKA`) trafiają do szablonów przez cache'owany context processor `uczelnia`; szablony i menu używają stockowych tagów/funkcji `django-polish-inflection`. Stara maszyneria (`deklinacja` list, `templatetags/deklinacja.py`, kolumny przypadków, wiersze `_PL`) znika.

**Tech Stack:** Django 5.2, Python ≥3.10, `django-polish-inflection>=0.1,<0.2` (→ `polish-inflection>=0.7.0`, dane SGJP), pytest + model_bakery, testcontainers (PostgreSQL/Redis auto), `uv run`.

## Global Constraints

- Wszystkie polecenia Pythona przez `uv run` — NIGDY goły `python`/`pytest`.
- Max długość linii: 88 znaków (ruff).
- NIGDY nie modyfikuj istniejących migracji w `src/*/migrations/` — tylko nowe.
- Baseline (`make baseline-update`) odświeżamy **raz, przy scalaniu do dev** — NIE w tym feature-branchu.
- Django template comments `{# … #}` jedno-liniowe (każda linia własne `{# #}`).
- `POLISH_INFLECTION_STRICT = False` w prod (słowo spoza SGJP → passthrough, nie błąd).
- Suita testów bywa wolna przy pierwszym uruchomieniu (cold start testcontainers) — ponów w razie timeoutu `page.goto` (nieistotne tutaj, brak Playwrighta).
- Przypadki jako przyjazne stringi: `mianownik/dopelniacz/celownik/biernik/narzednik/miejscownik/wolacz`; liczba: `liczba="mnoga"`.

---

## File Structure

- `pyproject.toml` — dodać zależność.
- `src/django_bpp/settings/base.py` — `INSTALLED_APPS` + `POLISH_INFLECTION_STRICT`.
- `src/bpp/nazwy.py` — **nowy**: `DOMYSLNE_LEMATY`, `lemat(uid)`.
- `src/bpp/context_processors/uczelnia.py` — 3 lematy do kontekstu + inwalidacja na zapis `Rzeczownik`.
- `src/django_bpp/menu.py` — `_tytul` + `_tytul_lazy`, `STRUKTURA_MENU`, usunięcie importu `jezyk_polski`.
- 4 szablony: `top_bar.html`, `browse/uczelnia.html`, `browse/jednostki.html`, `browse/jednostki_modern_bordered.html`.
- `src/bpp/templatetags/deklinacja.py` — **usunąć**.
- `src/bpp/jezyk_polski.py` — usunąć `deklinacja`, `znajdz_rzeczownik`, `lazy_rzeczownik_title`.
- `src/bpp/models/rzeczownik.py` — odchudzić do `uid` + `m` (+ property `mianownik`).
- `src/bpp/admin/__init__.py` — uprościć `RzeczownikAdmin`.
- `src/bpp/migrations/0445_rzeczownik_tylko_mianownik.py` — **nowy**.
- Testy: `src/bpp/tests/test_nazwy.py` (nowy), `src/bpp/tests/test_context_processor_nazwy.py` (nowy), `src/bpp/tests/test_menu_nazwy.py` (nowy), `src/bpp/tests/test_odmiana_integracja.py` (nowy), `src/bpp/tests/test_models/test_rzeczownik.py` (przepisać), `src/bpp/tests/test_no_deklinacja.py` (nowy grep-guard).

---

### Task 1: Zależność + ustawienia

**Files:**
- Modify: `pyproject.toml:32` (blok `dependencies`)
- Modify: `src/django_bpp/settings/base.py:356` (INSTALLED_APPS), `:1395` (nowe ustawienie)

**Interfaces:**
- Produces: dostępny import `polish_inflection` (`odmien`, `MIANOWNIK`, `MNOGA`, `odmien_lub_wyraz`) oraz tagi szablonowe `{% load polish_inflection %}`.

- [ ] **Step 1: Dodaj zależność do `pyproject.toml`**

W bloku `dependencies = [` (po linii `"Django>=5.2.15,<5.3",`) dodaj:

```toml
    "django-polish-inflection>=0.1,<0.2",
```

- [ ] **Step 2: Zainstaluj**

Run: `uv sync`
Expected: rozwiązuje i instaluje `django-polish-inflection`, `polish-inflection`, `polish-inflection-data`, `marisa-trie`.

- [ ] **Step 3: Dodaj aplikację do INSTALLED_APPS**

W `src/django_bpp/settings/base.py`, w liście `INSTALLED_APPS` (po `"tinymce",`, linia ~364) dodaj:

```python
    "django_polish_inflection",
```

- [ ] **Step 4: Dodaj ustawienie STRICT**

W `src/django_bpp/settings/base.py` po linii `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW = env("DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW")` (~1395) dodaj:

```python

# polish-inflection: słowo spoza słownika SGJP → passthrough (nie błąd renderu)
POLISH_INFLECTION_STRICT = False
```

- [ ] **Step 5: Weryfikacja silnika + system check**

Najpierw potwierdź nazwy stałych (Task 5 używa `MIANOWNIK`/`MNOGA`):

Run: `uv run python -c "import polish_inflection as p; print(sorted(n for n in dir(p) if n.isupper()))"`
Expected: lista zawiera m.in. `'MIANOWNIK'`, `'MNOGA'` (oraz pozostałe przypadki). Jeśli `MIANOWNIK` nie występuje — użyj faktycznej nazwy stałej mianownika z tej listy w Tasku 5.

Run: `uv run python -c "from polish_inflection import odmien, MIANOWNIK, MNOGA; print(odmien('jednostka', MIANOWNIK, MNOGA))"`
Expected: `jednostki`

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/django_bpp/settings/base.py
git commit -m "feat(odmiana): dodaj django-polish-inflection (silnik SGJP) + ustawienia"
```

---

### Task 2: Resolver lematów `bpp/nazwy.py`

**Files:**
- Create: `src/bpp/nazwy.py`
- Test: `src/bpp/tests/test_nazwy.py`

**Interfaces:**
- Produces: `bpp.nazwy.lemat(uid: str) -> str` (mianownik z `Rzeczownik` albo default); `bpp.nazwy.DOMYSLNE_LEMATY: dict[str, str]` z kluczami `"UCZELNIA"`, `"WYDZIAL"`, `"JEDNOSTKA"`.

- [ ] **Step 1: Napisz failing test**

Create `src/bpp/tests/test_nazwy.py`:

```python
import pytest

from bpp.nazwy import DOMYSLNE_LEMATY, lemat


@pytest.mark.django_db
def test_lemat_z_zasianego_wiersza():
    # migracja 0362 zasiewa UCZELNIA/WYDZIAL/JEDNOSTKA
    assert lemat("JEDNOSTKA") == "jednostka"


@pytest.mark.django_db
def test_lemat_override_przemianowanie():
    from bpp.models import Rzeczownik

    Rzeczownik.objects.filter(uid="JEDNOSTKA").update(m="dział")
    assert lemat("JEDNOSTKA") == "dział"


@pytest.mark.django_db
def test_lemat_brak_wiersza_uzywa_domyslnego():
    from bpp.models import Rzeczownik

    Rzeczownik.objects.filter(uid="JEDNOSTKA").delete()
    assert lemat("JEDNOSTKA") == DOMYSLNE_LEMATY["JEDNOSTKA"]
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/bpp/tests/test_nazwy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bpp.nazwy'`

- [ ] **Step 3: Zaimplementuj `bpp/nazwy.py`**

Create `src/bpp/nazwy.py`:

```python
"""Źródło lematów (mianownik l.poj.) dla generycznych nazw struktury.

Odmianę zapewnia ``polish-inflection`` — tu dostarczamy tylko mianownik,
z per-install override w modelu ``Rzeczownik`` albo z wartości domyślnej.
"""

DOMYSLNE_LEMATY = {
    "UCZELNIA": "uczelnia",
    "WYDZIAL": "wydział",
    "JEDNOSTKA": "jednostka",
}


def lemat(uid):
    """Mianownik (lemat) dla ``uid``: override z ``Rzeczownik`` albo default."""
    from bpp.models import Rzeczownik

    row = Rzeczownik.objects.filter(uid=uid).first()
    return row.m if row is not None else DOMYSLNE_LEMATY[uid]
```

- [ ] **Step 4: Uruchom — ma przejść**

Run: `uv run pytest src/bpp/tests/test_nazwy.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bpp/nazwy.py src/bpp/tests/test_nazwy.py
git commit -m "feat(odmiana): resolver lematow bpp.nazwy.lemat (override Rzeczownik + default)"
```

---

### Task 3: Lematy w context processorze + inwalidacja

**Files:**
- Modify: `src/bpp/context_processors/uczelnia.py`
- Test: `src/bpp/tests/test_context_processor_nazwy.py`

**Interfaces:**
- Consumes: `bpp.nazwy.lemat`.
- Produces: kontekst szablonów zawiera `nazwa_uczelni`, `nazwa_wydzialu`, `nazwa_jednostki` (stringi-lematy).

- [ ] **Step 1: Napisz failing test**

Create `src/bpp/tests/test_context_processor_nazwy.py`:

```python
import pytest
from django.test import RequestFactory

from bpp.context_processors.uczelnia import uczelnia


@pytest.mark.django_db
def test_context_processor_dostarcza_lematy(settings):
    from django.core.cache import cache

    cache.delete(b"bpp_uczelnia")
    ctx = uczelnia(RequestFactory().get("/"))
    assert ctx["nazwa_uczelni"] == "uczelnia"
    assert ctx["nazwa_wydzialu"] == "wydział"
    assert ctx["nazwa_jednostki"] == "jednostka"


@pytest.mark.django_db
def test_zapis_rzeczownika_inwaliduje_cache():
    from django.core.cache import cache

    from bpp.models import Rzeczownik

    cache.delete(b"bpp_uczelnia")
    uczelnia(RequestFactory().get("/"))  # zasiej cache
    Rzeczownik.objects.filter(uid="JEDNOSTKA").update(m="dział")
    # sam update() nie woła save(); wołamy zapis pełnego obiektu:
    obj = Rzeczownik.objects.get(uid="JEDNOSTKA")
    obj.save()
    ctx = uczelnia(RequestFactory().get("/"))
    assert ctx["nazwa_jednostki"] == "dział"
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/bpp/tests/test_context_processor_nazwy.py -v`
Expected: FAIL — `KeyError: 'nazwa_uczelni'`

- [ ] **Step 3: Zmodyfikuj `context_processors/uczelnia.py`**

Dodaj na górze (po `from bpp.models.struktura import Uczelnia`):

```python
from bpp.models.rzeczownik import Rzeczownik
from bpp.nazwy import lemat
```

Dodaj helper przed `def uczelnia(request):`:

```python
def _lematy():
    return {
        "nazwa_uczelni": lemat("UCZELNIA"),
        "nazwa_wydzialu": lemat("WYDZIAL"),
        "nazwa_jednostki": lemat("JEDNOSTKA"),
    }
```

Zamień ciało `uczelnia` (od `u = Uczelnia...` w dół) na:

```python
    u = Uczelnia.objects.get_for_request(request)
    if u is None:
        return {"uczelnia": NiezdefiniowanaUczelnia, **_lematy()}

    value = {"uczelnia": u, **_lematy()}
    cache.set(b"bpp_uczelnia", (time.time() + 3600, value))
    return value
```

Dodaj drugi receiver (po `invalidate_uczelnia_caches`):

```python
@receiver(post_save, sender=Rzeczownik)
def invalidate_lematy_cache(*args, **kw):
    """Zmiana nazwy w Rzeczowniku ma natychmiast odświeżyć lematy w kontekście."""
    cache.delete(b"bpp_uczelnia")
```

- [ ] **Step 4: Uruchom — ma przejść**

Run: `uv run pytest src/bpp/tests/test_context_processor_nazwy.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bpp/context_processors/uczelnia.py src/bpp/tests/test_context_processor_nazwy.py
git commit -m "feat(odmiana): lematy nazw w context processorze + inwalidacja na zapis Rzeczownika"
```

---

### Task 4: Migracja szablonów na silnik

**Files:**
- Modify: `src/django_bpp/templates/top_bar.html`
- Modify: `src/bpp/templates/browse/uczelnia.html`
- Modify: `src/bpp/templates/browse/jednostki.html`
- Modify: `src/bpp/templates/browse/jednostki_modern_bordered.html`
- Test: `src/bpp/tests/test_odmiana_integracja.py`

**Interfaces:**
- Consumes: zmienne kontekstu `nazwa_uczelni/nazwa_wydzialu/nazwa_jednostki` (Task 3), tagi `{% load polish_inflection %}` (Task 1).

- [ ] **Step 1: Napisz failing test integracyjny silnika w BPP**

Create `src/bpp/tests/test_odmiana_integracja.py`:

```python
from django.template import Context, Template


def _render(src, **ctx):
    return Template("{% load polish_inflection %}" + src).render(Context(ctx))


def test_odmien_dopelniacz_mnoga():
    assert _render('{% odmien nazwa "dopelniacz" liczba="mnoga" %}',
                   nazwa="jednostka") == "jednostek"


def test_odmien_biernik_pojedyncza():
    assert _render('{% odmien nazwa "biernik" %}', nazwa="jednostka") == "jednostkę"


def test_liczebnikowa_2_daje_mianownik_mnogi_poprawny():
    # regresja live-buga: dawniej "2 jednostek", teraz "2 jednostki"
    assert _render("{% odmiana_liczebnikowa nazwa 2 %}", nazwa="jednostka") == "jednostki"


def test_liczebnikowa_5():
    assert _render("{% odmiana_liczebnikowa nazwa 5 %}", nazwa="jednostka") == "jednostek"


def test_odmien_dziala_na_przemianowanym_lemacie():
    assert _render('{% odmien nazwa "dopelniacz" liczba="mnoga" %}',
                   nazwa="dział") == "działów"
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/bpp/tests/test_odmiana_integracja.py -v`
Expected: FAIL — `'polish_inflection' is not a registered tag library` (jeśli Task 1 pominięty) LUB PASS jeśli Task 1 gotowy. Jeśli PASS — to znaczy silnik działa; przejdź dalej (test dokumentuje kontrakt).

- [ ] **Step 3: `top_bar.html`**

W `src/django_bpp/templates/top_bar.html`:
- linia 46: zamień `{% load deklinacja %}` → `{% load polish_inflection %}`
- linia 47: zamień `{% rzeczownik_uczelnia %}` → `{% odmien nazwa_uczelni "mianownik" %}`
- linia 48: zamień `{% rzeczownik_jednostki_m %}` → `{% odmien nazwa_jednostki "mianownik" liczba="mnoga" %}`

- [ ] **Step 4: `browse/uczelnia.html`**

W `src/bpp/templates/browse/uczelnia.html`:
- linia 2: w tagu `{% load user_in_group deklinacja cache media_utils static prace %}` zamień słowo `deklinacja` na `polish_inflection`.
- linie 483 i 519: zamień `{% load deklinacja %}` → `{% load polish_inflection %}`.
- wszystkie `{% rzeczownik_wydział %}` → `{% odmien nazwa_wydzialu "biernik" %}` (replace_all).
- wszystkie `{% rzeczownik_jednostkę %}` → `{% odmien nazwa_jednostki "biernik" %}` (replace_all).

- [ ] **Step 5: `browse/jednostki.html`**

W `src/bpp/templates/browse/jednostki.html`:
- linia 1: zamień `{% load deklinacja %}` → `{% load polish_inflection %}`.
- `{% rzeczownik_jednostki %}` → `{% odmien nazwa_jednostki "mianownik" liczba="mnoga" %}` (replace_all).
- `{% rzeczownik_jednostek_d %}` → `{% odmien nazwa_jednostki "dopelniacz" liczba="mnoga" %}` (replace_all).
- `{% rzeczownik_jednostki_w %}` → `{% odmien nazwa_jednostki "wolacz" liczba="mnoga" %}` (replace_all).
- Blok liczebnikowy (linia 159) — zamień dokładnie:

```
                ({{ paginator.count }} {% if paginator.count == 1 %}{% rzeczownik_jednostka %}{% elif paginator.count < 5 %}{% rzeczownik_jednostek_d %}{% else %}{% rzeczownik_jednostek_d %}{% endif %})
```

na:

```
                ({{ paginator.count }} {% odmiana_liczebnikowa nazwa_jednostki paginator.count %})
```

- [ ] **Step 6: `browse/jednostki_modern_bordered.html`**

Powtórz Step 5 dla `src/bpp/templates/browse/jednostki_modern_bordered.html` (linia 1 load; te same `{% rzeczownik_* %}`; blok liczebnikowy w linii 149 — identyczny string jak wyżej → ta sama zamiana).

- [ ] **Step 7: Uruchom testy + check**

Run: `uv run pytest src/bpp/tests/test_odmiana_integracja.py -v`
Expected: PASS (5 passed)

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 8: Commit**

```bash
git add src/django_bpp/templates/top_bar.html src/bpp/templates/browse/uczelnia.html src/bpp/templates/browse/jednostki.html src/bpp/templates/browse/jednostki_modern_bordered.html src/bpp/tests/test_odmiana_integracja.py
git commit -m "feat(odmiana): szablony na {% odmien %}/{% odmiana_liczebnikowa %} (fix '2 jednostek')"
```

---

### Task 5: Migracja menu admina

**Files:**
- Modify: `src/django_bpp/menu.py`
- Test: `src/bpp/tests/test_menu_nazwy.py`

**Interfaces:**
- Consumes: `bpp.nazwy.lemat`, `polish_inflection.odmien_lub_wyraz/MIANOWNIK/MNOGA`.
- Produces: `STRUKTURA_MENU` z leniwymi etykietami; `django_bpp.menu._tytul(uid, liczba=None) -> str`.

- [ ] **Step 1: Napisz failing test**

Create `src/bpp/tests/test_menu_nazwy.py`:

```python
import pytest


@pytest.mark.django_db
def test_struktura_menu_domyslne_etykiety():
    from django_bpp.menu import STRUKTURA_MENU

    assert str(STRUKTURA_MENU[0][0]) == "Uczelnia"
    assert str(STRUKTURA_MENU[1][0]) == "Wydziały"
    assert str(STRUKTURA_MENU[2][0]) == "Jednostki"


@pytest.mark.django_db
def test_struktura_menu_po_przemianowaniu():
    from django_bpp.menu import STRUKTURA_MENU
    from bpp.models import Rzeczownik

    Rzeczownik.objects.filter(uid="JEDNOSTKA").update(m="dział")
    assert str(STRUKTURA_MENU[2][0]) == "Działy"
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/bpp/tests/test_menu_nazwy.py -v`
Expected: FAIL — dziś etykieta `STRUKTURA_MENU[1][0]` liczy się przez `lazy_rzeczownik_title` (inny mechanizm) i/lub `AttributeError` po zmianie importów.

- [ ] **Step 3: Zmień importy i dodaj helper w `menu.py`**

W `src/django_bpp/menu.py` usuń linię `from bpp import jezyk_polski` i dodaj:

```python
from django.template.defaultfilters import capfirst
from django.utils.functional import lazy as _lazy
from polish_inflection import MIANOWNIK, MNOGA, odmien_lub_wyraz

from bpp.nazwy import lemat


def _tytul(uid, liczba=None):
    return capfirst(odmien_lub_wyraz(lemat(uid), MIANOWNIK, liczba))


_tytul_lazy = _lazy(_tytul, str)
```

- [ ] **Step 4: Zamień `STRUKTURA_MENU`**

Zamień blok:

```python
STRUKTURA_MENU = [
    (jezyk_polski.lazy_rzeczownik_title("UCZELNIA"), "/admin/bpp/uczelnia/"),
    (jezyk_polski.lazy_rzeczownik_title("WYDZIAL_PL"), "/admin/bpp/wydzial/"),
    (jezyk_polski.lazy_rzeczownik_title("JEDNOSTKA_PL"), "/admin/bpp/jednostka/"),
    ("Kierunki studiów", "/admin/bpp/kierunek_studiow/"),
]
```

na:

```python
STRUKTURA_MENU = [
    (_tytul_lazy("UCZELNIA"), "/admin/bpp/uczelnia/"),
    (_tytul_lazy("WYDZIAL", MNOGA), "/admin/bpp/wydzial/"),
    (_tytul_lazy("JEDNOSTKA", MNOGA), "/admin/bpp/jednostka/"),
    ("Kierunki studiów", "/admin/bpp/kierunek_studiow/"),
]
```

(`_should_hide_wydzial` indeksuje `STRUKTURA_MENU[1][1]` — URL, bez zmian — więc działa dalej.)

- [ ] **Step 5: Uruchom — ma przejść**

Run: `uv run pytest src/bpp/tests/test_menu_nazwy.py -v`
Expected: PASS (2 passed)

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 6: Commit**

```bash
git add src/django_bpp/menu.py src/bpp/tests/test_menu_nazwy.py
git commit -m "feat(odmiana): menu Struktura na silnik (leniwe etykiety z lematow)"
```

---

### Task 6: Usunięcie martwej maszynerii deklinacji

**Files:**
- Delete: `src/bpp/templatetags/deklinacja.py`
- Modify: `src/bpp/jezyk_polski.py`
- Test: `src/bpp/tests/test_no_deklinacja.py`

**Interfaces:**
- Consumes: nic (usuwamy). Po tym kroku żaden szablon/menu nie referuje starych symboli.

- [ ] **Step 1: Napisz grep-guard test**

Create `src/bpp/tests/test_no_deklinacja.py`:

```python
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # korzeń repo
# ten plik trzyma wzorce jako literały — wykluczamy go, by nie łapał sam siebie
SELF = "src/bpp/tests/test_no_deklinacja.py"


def _grep(pattern, pathspec):
    res = subprocess.run(
        ["git", "grep", "-n", pattern, "--", pathspec, f":(exclude){SELF}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return res.stdout.strip()


def test_brak_starych_tagow_rzeczownik():
    assert _grep(r"{% rzeczownik_", "*.html") == ""


def test_brak_load_deklinacja():
    assert _grep(r"{% load deklinacja", "*.html") == ""


def test_brak_definicji_deklinacji_w_py():
    # wzorce w formie definicji, by nie łapać zwykłych referencji
    assert _grep("def znajdz_rzeczownik", "*.py") == ""
    assert _grep("def lazy_rzeczownik_title", "*.py") == ""
    assert _grep("^deklinacja = ", "*.py") == ""
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/bpp/tests/test_no_deklinacja.py -v`
Expected: FAIL — stare tagi/symbole jeszcze istnieją.

- [ ] **Step 3: Usuń plik template-tagów**

```bash
git rm src/bpp/templatetags/deklinacja.py
```

- [ ] **Step 4: Odchudź `jezyk_polski.py`**

W `src/bpp/jezyk_polski.py` usuń: całą listę `deklinacja = [...]` (linie 5–41), funkcję `znajdz_rzeczownik` (44–48) i funkcję `lazy_rzeczownik_title` (51–64). **Zostaw** `czasownik_byc` i `warianty_zapisanego_nazwiska`. Docstring modułu zostaje.

- [ ] **Step 5: Uruchom guard + szersze testy**

Run: `uv run pytest src/bpp/tests/test_no_deklinacja.py src/bpp/tests/test_odmiana_integracja.py src/bpp/tests/test_menu_nazwy.py src/bpp/tests/test_util/test_jezyk_polski.py -v`
Expected: PASS (wszystkie)

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(odmiana): usun martwa maszynerie deklinacji (templatetag + tabela w jezyk_polski)"
```

---

### Task 7: Odchudzenie modelu Rzeczownik + migracja + admin

**Files:**
- Modify: `src/bpp/models/rzeczownik.py`
- Modify: `src/bpp/admin/__init__.py:95-110`
- Create: `src/bpp/migrations/0445_rzeczownik_tylko_mianownik.py`
- Test: `src/bpp/tests/test_models/test_rzeczownik.py` (przepisać)

**Interfaces:**
- Produces: `Rzeczownik(uid, m)` + property `mianownik`; brak wierszy `_PL`; brak kolumn `d/c/b/n/ms/w`.

- [ ] **Step 1: Przepisz test modelu**

Zastąp całą treść `src/bpp/tests/test_models/test_rzeczownik.py`:

```python
import pytest
from model_bakery import baker

from bpp.models import Rzeczownik


@pytest.mark.django_db
def test_rzeczownik_str():
    r = baker.make(Rzeczownik, uid="JEDNOSTKA", m="dział")
    assert str(r) == "Rzeczownik JEDNOSTKA = dział"


@pytest.mark.django_db
def test_rzeczownik_mianownik_alias():
    r = baker.make(Rzeczownik, uid="WYDZIAL", m="klinika")
    assert r.mianownik == "klinika"


@pytest.mark.django_db
def test_wiersze_pl_usuniete():
    assert not Rzeczownik.objects.filter(uid__endswith="_PL").exists()
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/bpp/tests/test_models/test_rzeczownik.py -v`
Expected: FAIL — stary `__str__` / istniejące wiersze `_PL`.

- [ ] **Step 3: Odchudź model**

Zastąp treść `src/bpp/models/rzeczownik.py`:

```python
from django.db import models


class Rzeczownik(models.Model):
    uid = models.CharField(max_length=20, primary_key=True)
    m = models.CharField(
        max_length=200,
        verbose_name="mianownik (lemat)",
        help_text=(
            "Mianownik liczby pojedynczej, np. „wydział" lub „dział". "
            "Pozostałe przypadki i liczbę mnogą generuje automatycznie "
            "polish-inflection."
        ),
    )

    @property
    def mianownik(self):
        return self.m

    class Meta:
        verbose_name_plural = "rzeczowniki"

    def __str__(self):
        return f"Rzeczownik {self.uid} = {self.m}"
```

- [ ] **Step 4: Uprość admin**

W `src/bpp/admin/__init__.py`, w klasie `RzeczownikAdmin` zamień:

```python
    list_display = ["uid", "m", "d", "c", "b", "n", "ms", "w"]
    search_fields = ["uid", "m", "d", "c", "b", "n", "ms", "w"]
```

na:

```python
    list_display = ["uid", "m"]
    search_fields = ["uid", "m"]
```

(`list_filter`, `readonly_fields`, `has_add_permission`, `has_delete_permission` zostają.)

- [ ] **Step 5: Napisz migrację**

Create `src/bpp/migrations/0445_rzeczownik_tylko_mianownik.py`:

```python
from django.db import migrations, models


def usun_wiersze_pl(apps, schema_editor):
    Rzeczownik = apps.get_model("bpp", "Rzeczownik")
    Rzeczownik.objects.filter(
        uid__in=["UCZELNIA_PL", "WYDZIAL_PL", "JEDNOSTKA_PL"]
    ).delete()


def noop(apps, schema_editor):
    # nieodwracalne: plural odtwarzalny z singularnego lematu przez silnik
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0444_alter_uczelnia_wyszukiwanie_rekordy_na_strone_anonim_and_more"),
    ]

    operations = [
        migrations.RemoveField(model_name="rzeczownik", name="d"),
        migrations.RemoveField(model_name="rzeczownik", name="c"),
        migrations.RemoveField(model_name="rzeczownik", name="b"),
        migrations.RemoveField(model_name="rzeczownik", name="n"),
        migrations.RemoveField(model_name="rzeczownik", name="ms"),
        migrations.RemoveField(model_name="rzeczownik", name="w"),
        migrations.AlterField(
            model_name="rzeczownik",
            name="m",
            field=models.CharField(
                max_length=200,
                verbose_name="mianownik (lemat)",
                help_text=(
                    "Mianownik liczby pojedynczej, np. „wydział" lub „dział". "
                    "Pozostałe przypadki i liczbę mnogą generuje automatycznie "
                    "polish-inflection."
                ),
            ),
        ),
        migrations.RunPython(usun_wiersze_pl, noop),
    ]
```

- [ ] **Step 6: Zweryfikuj brak dryfu migracji**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run bpp`
Expected: `No changes detected` (model zgadza się z migracjami)

- [ ] **Step 7: Uruchom testy modelu + resolver + kontekst**

Run: `uv run pytest src/bpp/tests/test_models/test_rzeczownik.py src/bpp/tests/test_nazwy.py src/bpp/tests/test_context_processor_nazwy.py src/bpp/tests/test_menu_nazwy.py -v`
Expected: PASS (wszystkie)

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(odmiana): Rzeczownik = tylko mianownik (usun kolumny przypadkow + wiersze _PL)"
```

---

### Task 8: Weryfikacja końcowa

**Files:** —

- [ ] **Step 1: System check + pełen zestaw testów odmiany**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check`
Expected: `System check identified no issues`

Run: `uv run pytest src/bpp/tests/test_nazwy.py src/bpp/tests/test_context_processor_nazwy.py src/bpp/tests/test_menu_nazwy.py src/bpp/tests/test_odmiana_integracja.py src/bpp/tests/test_no_deklinacja.py src/bpp/tests/test_models/test_rzeczownik.py src/bpp/tests/test_util/test_jezyk_polski.py -v`
Expected: PASS (wszystkie)

- [ ] **Step 2: Lint**

Run: `uv run ruff check src/bpp/nazwy.py src/bpp/context_processors/uczelnia.py src/django_bpp/menu.py src/bpp/models/rzeczownik.py src/bpp/admin/__init__.py`
Expected: `All checks passed!`

Run: `uv run ruff format --check src/bpp/nazwy.py`
Expected: brak zmian

- [ ] **Step 3: Wizualna weryfikacja (opcjonalnie, jeśli dostępny run-site)**

Run: `uv run run-site run --no-browser --no-celery` (w tle), otwórz stronę główną i `/admin/` — sprawdź górny pasek (menu jednostek) i menu „Struktura" w adminie. Zmień w `/admin/bpp/rzeczownik/` `JEDNOSTKA` → „dział" i potwierdź, że etykiety się odmieniają („Działy", „5 działów").

- [ ] **Step 4: Push + PR (po akceptacji)**

```bash
git push -u origin feat/odmiana-rodzaj-instytucji
```

Newsfragment towncrier + PR — po potwierdzeniu przez użytkownika. **Baseline (`make baseline-update`) i newsfragment przy scalaniu do dev.**

---

## Notatki wdrożeniowe

- **Kolejność jest istotna:** Task 6 (usunięcie starej maszynerii) i Task 7 (odchudzenie modelu) MUSZĄ iść po Taskach 4–5 (migracja konsumentów) — inaczej szablony/menu tracą działające tagi.
- **`git grep`** w Task 6 działa względem indeksu — po `git rm`/edycji symbole znikają; uruchamiaj guard po edycjach.
- **Znaki polskie w help_text** (`„…"`) muszą być identyczne w modelu i w `AlterField` migracji, inaczej `makemigrations --check` wykryje dryf.
