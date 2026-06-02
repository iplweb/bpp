# Eksplorator sieci współautorstwa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać na stronie autora interaktywny, progresywnie rozwijany graf sieci współautorstwa (Cytoscape.js), zasilany endpointem JSON, i usunąć stary prototyp wizualizacji.

**Architecture:** Endpoint JSON zwraca sąsiadów dowolnego autora (ten sam endpoint dla centrum i każdego rozwinięcia, filtr `pokazuj=True`). Statyczny moduł JS (Cytoscape + fcose) fetchuje dane, renderuje ego-sieć i animowanie dorzuca współautorów po kliknięciu węzła. Biblioteka ładowana lazy osobnym bundlem tylko na stronie grafu. Przelicznik `AuthorConnection` dopięty do celerybeat.

**Tech Stack:** Django, Celery, pytest + model_bakery, Cytoscape.js 3 + cytoscape-fcose, esbuild (Grunt), Foundation CSS.

**Spec:** `docs/superpowers/specs/2026-06-02-powiazania-autorow-eksplorator-design.md`

**Branch:** `powiazania-autorow-eksplorator` (już utworzona, spec zacommitowany).

---

## Struktura plików

Tworzone:
- `src/powiazania_autorow/test_views.py` — testy endpointu i strony.
- `src/powiazania_autorow/templates/powiazania_autorow/graf.html` — strona eksploratora.
- `src/bpp/static/bpp/js/cytoscape-entry.js` — entry esbuild dla osobnego bundla.
- `src/bpp/static/bpp/js/visualizations/powiazania-autorow.js` — logika eksploratora.

Modyfikowane:
- `src/powiazania_autorow/views.py` — z pustego stuba na dwa widoki.
- `src/bpp/urls.py` — dwie trasy pod namespace `bpp`.
- `src/bpp/views/browse.py` — `AutorView.get_context_data` (+ `ma_powiazania`).
- `src/bpp/templates/browse/autor.html` — przycisk „Zobacz sieć powiązań".
- `src/django_bpp/settings/base.py` — wpis w `CELERYBEAT_SCHEDULE`.
- `package.json` — `cytoscape`, `cytoscape-fcose`.
- `Gruntfile.js` — drugi krok esbuild + do tasków build.

Usuwane:
- `src/powiazania_autorow/visualization/` (cały katalog).
- `src/powiazania_autorow/management/commands/generate_author_connections_viz.py`.
- `src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.js`.
- `src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.html`.
- `src/bpp/static/bpp/js/visualizations/author-connections-ui.js`.

---

### Task 1: Usunięcie starego prototypu wizualizacji

**Files:**
- Delete: `src/powiazania_autorow/visualization/` (cały katalog: `__init__.py`, `data.py`, `html.py`, `js.py`)
- Delete: `src/powiazania_autorow/management/commands/generate_author_connections_viz.py`
- Delete: `src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.js`
- Delete: `src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.html`
- Delete: `src/bpp/static/bpp/js/visualizations/author-connections-ui.js`

- [ ] **Step 1: Potwierdź brak innych konsumentów**

Run: `grep -rn "powiazania_autorow.visualization\|from .visualization\|from ..visualization\|generate_sigma\|generate_visualization_html\|author-connections-ui\|author_connections" src/ --include=*.py --include=*.html --include=*.js | grep -v "src/powiazania_autorow/visualization/" | grep -v "src/django_bpp/bpp/static/bpp/js/visualizations/author_connections"`
Expected: brak wyników (jedyny konsument — usuwana komenda zarządzająca).

- [ ] **Step 2: Usuń pliki**

```bash
git rm -r src/powiazania_autorow/visualization/
git rm src/powiazania_autorow/management/commands/generate_author_connections_viz.py
git rm src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.js
git rm src/django_bpp/bpp/static/bpp/js/visualizations/author_connections.html
git rm src/bpp/static/bpp/js/visualizations/author-connections-ui.js
```

- [ ] **Step 3: Uruchom istniejące testy apki (muszą zostać zielone)**

Run: `uv run pytest src/powiazania_autorow/tests.py -q`
Expected: PASS (testy importują tylko `core`, `models`, `tasks`).

- [ ] **Step 4: Sprawdź, że Django się ładuje (komenda zniknęła czysto)**

Run: `uv run python src/manage.py check`
Expected: „System check identified no issues".

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(powiazania_autorow): usuń prototyp wizualizacji (generowanie JS f-stringiem)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Endpoint JSON z sąsiadami autora (TDD)

**Files:**
- Test: `src/powiazania_autorow/test_views.py`
- Modify: `src/powiazania_autorow/views.py`
- Modify: `src/bpp/urls.py`

- [ ] **Step 1: Napisz testy endpointu danych**

Utwórz `src/powiazania_autorow/test_views.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from powiazania_autorow.models import AuthorConnection


@pytest.mark.django_db
def test_dane_zwraca_centrum_i_sasiadow_posortowanych(client):
    centrum = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    a = baker.make(Autor, imiona="Anna", nazwisko="Nowak", pokazuj=True)
    b = baker.make(Autor, imiona="Bob", nazwisko="Zet", pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=2
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=b, shared_publications_count=9
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    resp = client.get(url)

    assert resp.status_code == 200
    data = resp.json()
    assert data["center"]["id"] == centrum.pk
    assert data["center"]["label"] == "Jan Kowalski"
    labels = [n["label"] for n in data["neighbors"]]
    assert labels == ["Bob Zet", "Anna Nowak"]
    assert data["neighbors"][0]["shared"] == 9


@pytest.mark.django_db
def test_dane_dziala_gdy_autor_jest_secondary(client):
    centrum = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    inny = baker.make(Autor, imiona="Ewa", nazwisko="Lis", pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=inny, secondary_author=centrum, shared_publications_count=4
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    assert [n["label"] for n in data["neighbors"]] == ["Ewa Lis"]


@pytest.mark.django_db
def test_dane_pomija_autorow_z_pokazuj_false(client):
    centrum = baker.make(Autor, pokazuj=True)
    ukryty = baker.make(Autor, imiona="X", nazwisko="Ukryty", pokazuj=False)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=ukryty, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    assert data["neighbors"] == []


@pytest.mark.django_db
def test_dane_pusty_gdy_brak_powiazan(client):
    centrum = baker.make(Autor, pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.json()["neighbors"] == []


@pytest.mark.django_db
def test_dane_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania_dane", args=[99999])
    assert client.get(url).status_code == 404
```

- [ ] **Step 2: Uruchom testy — muszą padać**

Run: `uv run pytest src/powiazania_autorow/test_views.py -q`
Expected: FAIL (`NoReverseMatch: 'browse_autor_powiazania_dane'` — trasa jeszcze nie istnieje).

- [ ] **Step 3: Zaimplementuj widok danych**

Zastąp zawartość `src/powiazania_autorow/views.py`:

```python
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import View

from bpp.models import Autor

from .models import AuthorConnection

# Bezpiecznik payloadu — suwak w UI i tak decyduje, ilu sąsiadów rysujemy.
MAKS_SASIADOW = 500


def _etykieta(autor):
    return f"{autor.imiona} {autor.nazwisko}".strip()


class GrafPowiazanDaneView(View):
    """JSON z sąsiadami (współautorami) danego autora.

    Ten sam endpoint obsługuje węzeł centralny i każde rozwinięcie po stronie
    klienta. Sąsiedzi filtrowani do pokazuj=True, sortowani malejąco po liczbie
    wspólnych publikacji.
    """

    def get(self, request, pk):
        autor = get_object_or_404(Autor, pk=pk)
        polaczenia = (
            AuthorConnection.objects.filter(
                Q(primary_author_id=pk) | Q(secondary_author_id=pk)
            )
            .select_related("primary_author", "secondary_author")
            .order_by("-shared_publications_count")
        )

        neighbors = []
        for c in polaczenia:
            inny = (
                c.secondary_author if c.primary_author_id == pk else c.primary_author
            )
            if not inny.pokazuj:
                continue
            neighbors.append(
                {
                    "id": inny.pk,
                    "label": _etykieta(inny),
                    "url": inny.get_absolute_url(),
                    "shared": c.shared_publications_count,
                }
            )
            if len(neighbors) >= MAKS_SASIADOW:
                break

        return JsonResponse(
            {
                "center": {
                    "id": autor.pk,
                    "label": _etykieta(autor),
                    "url": autor.get_absolute_url(),
                },
                "neighbors": neighbors,
            }
        )
```

- [ ] **Step 4: Dodaj trasę do `src/bpp/urls.py`**

Dodaj import obok pozostałych importów widoków z innych apek (po linii z `ranking_autorow.views`, ~98):

```python
from powiazania_autorow.views import GrafPowiazanDaneView
```

Dodaj wzorzec tuż po istniejącej trasie `browse_autor`
(`url(r"^autor/(?P<pk>\d+)/$", AutorView.as_view(), name="browse_autor")`):

```python
    url(
        r"^autor/(?P<pk>\d+)/powiazania/dane\.json$",
        GrafPowiazanDaneView.as_view(),
        name="browse_autor_powiazania_dane",
    ),
```

- [ ] **Step 5: Uruchom testy — muszą przejść**

Run: `uv run pytest src/powiazania_autorow/test_views.py -q`
Expected: PASS (5 testów).

- [ ] **Step 6: Commit**

```bash
git add src/powiazania_autorow/views.py src/powiazania_autorow/test_views.py src/bpp/urls.py
git commit -m "feat(powiazania_autorow): endpoint JSON z sąsiadami autora

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Strona eksploratora (widok + szablon szkielet) (TDD)

**Files:**
- Modify: `src/powiazania_autorow/views.py`
- Modify: `src/bpp/urls.py`
- Create: `src/powiazania_autorow/templates/powiazania_autorow/graf.html`
- Test: `src/powiazania_autorow/test_views.py`

- [ ] **Step 1: Dopisz test strony**

Dodaj do `src/powiazania_autorow/test_views.py`:

```python
@pytest.mark.django_db
def test_strona_grafu_renderuje_kontener(client):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania", args=[autor.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert 'id="cytoscape-container"' in tresc
    assert f'data-autor-id="{autor.pk}"' in tresc


@pytest.mark.django_db
def test_strona_grafu_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania", args=[99999])
    assert client.get(url).status_code == 404
```

- [ ] **Step 2: Uruchom — padają**

Run: `uv run pytest src/powiazania_autorow/test_views.py -k strona -q`
Expected: FAIL (`NoReverseMatch: 'browse_autor_powiazania'`).

- [ ] **Step 3: Dodaj widok strony**

Dopisz do `src/powiazania_autorow/views.py` (import `TemplateView` i klasa):

Zmień linię importu widoków na:

```python
from django.views.generic import TemplateView, View
```

Dodaj klasę:

```python
class GrafPowiazanView(TemplateView):
    """Strona z interaktywnym grafem powiązań autora."""

    template_name = "powiazania_autorow/graf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["autor"] = get_object_or_404(Autor, pk=kwargs["pk"])
        return context
```

- [ ] **Step 4: Dodaj trasę strony do `src/bpp/urls.py`**

Rozszerz import:

```python
from powiazania_autorow.views import GrafPowiazanDaneView, GrafPowiazanView
```

Dodaj wzorzec przed trasą `browse_autor_powiazania_dane`:

```python
    url(
        r"^autor/(?P<pk>\d+)/powiazania/$",
        GrafPowiazanView.as_view(),
        name="browse_autor_powiazania",
    ),
```

- [ ] **Step 5: Utwórz szablon szkielet**

Utwórz `src/powiazania_autorow/templates/powiazania_autorow/graf.html`:

```django
{% extends "base.html" %}
{% load static %}

{% block extratitle %}Sieć powiązań — {{ autor }}{% endblock %}

{% block breadcrumbs %}
    {{ block.super }}
    <li><a href="{% url "bpp:browse_autorzy" %}">Autorzy</a></li>
    <li><a href="{{ autor.get_absolute_url }}">{{ autor }}</a></li>
    <li class="current">Sieć powiązań</li>
{% endblock %}

{% block content %}
    <h1>Sieć powiązań — {{ autor }}</h1>
    <p class="graf-pomoc">
        Najedź na węzeł, aby zobaczyć autora. Kliknij, aby rozwinąć jego
        współautorów. Grubość linii odpowiada liczbie wspólnych publikacji.
    </p>

    <div class="graf-controls">
        <label for="graf-topn">
            Maks. współautorów na węzeł: <span id="graf-topn-label">15</span>
        </label>
        <input type="range" id="graf-topn" min="3" max="50" value="15" step="1">
    </div>

    <div id="graf-wrapper" style="position: relative;">
        <div id="cytoscape-container"
             data-autor-id="{{ autor.pk }}"
             data-autor-label="{{ autor.imiona }} {{ autor.nazwisko }}"
             data-dane-url-template="{% url 'bpp:browse_autor_powiazania_dane' 0 %}"
             style="width: 100%; height: 75vh; border: 1px solid #ccc;
                    background: #fff;"></div>
        <div id="graf-tooltip"
             style="position: absolute; display: none; pointer-events: none;
                    background: rgba(255,255,255,.95); border: 1px solid #ddd;
                    border-radius: 4px; padding: 4px 8px; font-size: 12px;
                    z-index: 1001;"></div>
        <div id="graf-panel"
             style="position: absolute; bottom: 10px; right: 10px; display: none;
                    background: rgba(255,255,255,.95); border: 1px solid #ddd;
                    border-radius: 4px; padding: 10px; font-size: 13px;
                    max-width: 280px; z-index: 1001;"></div>
        <p id="graf-empty" style="display: none;">
            Brak zarejestrowanych powiązań — dane przeliczane są raz na dobę.
        </p>
    </div>

    <script src="{% static 'bpp/js/dist/cytoscape-bundle.js' %}"></script>
    <script src="{% static 'bpp/js/visualizations/powiazania-autorow.js' %}"></script>
{% endblock %}
```

Uwaga: `cytoscape-bundle.js` i `powiazania-autorow.js` powstają w Tasku 6 i 7 — na tym etapie strona renderuje kontener, a skrypty (jeszcze nieistniejące pliki) dają 404 w konsoli; test sprawdza tylko HTML.

- [ ] **Step 6: Uruchom testy strony — przechodzą**

Run: `uv run pytest src/powiazania_autorow/test_views.py -k strona -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/powiazania_autorow/views.py src/powiazania_autorow/test_views.py src/bpp/urls.py src/powiazania_autorow/templates/
git commit -m "feat(powiazania_autorow): strona eksploratora grafu powiązań

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Kontekst `ma_powiazania` + przycisk na stronie autora (TDD)

**Files:**
- Modify: `src/bpp/views/browse.py:147-152`
- Test: `src/powiazania_autorow/test_views.py`
- Modify: `src/bpp/templates/browse/autor.html:22-39`

- [ ] **Step 1: Dopisz test kontekstu**

Dodaj do `src/powiazania_autorow/test_views.py`:

```python
@pytest.mark.django_db
def test_strona_autora_ma_flage_powiazan_true(client):
    centrum = baker.make(Autor, pokazuj=True)
    sasiad = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=sasiad, shared_publications_count=1
    )
    resp = client.get(reverse("bpp:browse_autor", args=[centrum.pk]))
    assert resp.status_code == 200
    assert resp.context["ma_powiazania"] is True


@pytest.mark.django_db
def test_strona_autora_ma_flage_powiazan_false(client):
    centrum = baker.make(Autor, pokazuj=True)
    resp = client.get(reverse("bpp:browse_autor", args=[centrum.pk]))
    assert resp.context["ma_powiazania"] is False
```

- [ ] **Step 2: Uruchom — padają**

Run: `uv run pytest src/powiazania_autorow/test_views.py -k flage -q`
Expected: FAIL (`KeyError: 'ma_powiazania'`).

- [ ] **Step 3: Rozszerz `AutorView.get_context_data`**

W `src/bpp/views/browse.py` dodaj import na górze (sekcja importów):

```python
from django.db.models import Q
```

(jeśli `Q` nie jest jeszcze importowane w tym pliku — sprawdź; jeśli jest, pomiń)

Zamień ciało `AutorView` (linie ~147-152):

```python
class AutorView(DetailView):
    template_name = "browse/autor.html"
    model = Autor

    def get_context_data(self, **kwargs):
        from powiazania_autorow.models import AuthorConnection

        ma_powiazania = AuthorConnection.objects.filter(
            Q(primary_author=self.object) | Q(secondary_author=self.object)
        ).exists()
        return super().get_context_data(
            typy=TYPY, ma_powiazania=ma_powiazania, **kwargs
        )
```

(import `AuthorConnection` lokalnie w metodzie — unika cykli importów przy ładowaniu apek.)

- [ ] **Step 4: Uruchom testy kontekstu — przechodzą**

Run: `uv run pytest src/powiazania_autorow/test_views.py -k flage -q`
Expected: PASS.

- [ ] **Step 5: Dodaj przycisk w szablonie autora**

W `src/bpp/templates/browse/autor.html`, w bloku `.autor-page__actions`
(po bloku edycji, przed zamknięciem `</div>` w linii ~38) dodaj:

```django
                {% if ma_powiazania %}
                    <a href="{% url 'bpp:browse_autor_powiazania' autor.pk %}"
                       class="jednostka-remap-button">
                        <span class="fi fi-share"></span>Zobacz sieć powiązań
                    </a>
                {% endif %}
```

- [ ] **Step 6: Render strony autora nadal działa**

Run: `uv run pytest src/powiazania_autorow/test_views.py -q`
Expected: PASS (wszystkie testy apki).

- [ ] **Step 7: Commit**

```bash
git add src/bpp/views/browse.py src/bpp/templates/browse/autor.html src/powiazania_autorow/test_views.py
git commit -m "feat(bpp): przycisk 'Zobacz sieć powiązań' na stronie autora

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Harmonogram przelicznika (celerybeat)

**Files:**
- Modify: `src/django_bpp/settings/base.py:670` (`CELERYBEAT_SCHEDULE`)
- Test: `src/powiazania_autorow/test_views.py`

- [ ] **Step 1: Dopisz test obecności wpisu w harmonogramie**

Dodaj do `src/powiazania_autorow/test_views.py`:

```python
def test_przelicznik_jest_w_celerybeat():
    from django.conf import settings

    nazwy_taskow = {
        wpis["task"] for wpis in settings.CELERYBEAT_SCHEDULE.values()
    }
    assert "powiazania_autorow.calculate_author_connections" in nazwy_taskow
```

- [ ] **Step 2: Uruchom — pada**

Run: `uv run pytest src/powiazania_autorow/test_views.py -k celerybeat -q`
Expected: FAIL (assert — task nieobecny).

- [ ] **Step 3: Dodaj wpis do `CELERYBEAT_SCHEDULE`**

W `src/django_bpp/settings/base.py`, wewnątrz słownika `CELERYBEAT_SCHEDULE`
(zaczyna się w linii 670), dodaj wpis przed zamykającym `}`:

```python
    "powiazania-autorow-przelicz-codziennie": {
        "task": "powiazania_autorow.calculate_author_connections",
        "schedule": crontab(hour=4, minute=0),  # Daily at 4 AM
    },
```

(`crontab` jest już zaimportowany — `base.py:13`.)

- [ ] **Step 4: Uruchom — przechodzi**

Run: `uv run pytest src/powiazania_autorow/test_views.py -k celerybeat -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/django_bpp/settings/base.py src/powiazania_autorow/test_views.py
git commit -m "feat(powiazania_autorow): codzienny przelicznik powiązań w celerybeat

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Lazy bundle Cytoscape (esbuild)

**Files:**
- Modify: `package.json:14-37` (dependencies)
- Create: `src/bpp/static/bpp/js/cytoscape-entry.js`
- Modify: `Gruntfile.js:220-238` (shell tasks) i `:248-260` (taski build)

- [ ] **Step 1: Dodaj zależności**

Run: `yarn add cytoscape cytoscape-fcose`
Expected: `package.json` dostaje `cytoscape` i `cytoscape-fcose` w `dependencies`; aktualizacja lockfile.

- [ ] **Step 2: Utwórz entry point**

Utwórz `src/bpp/static/bpp/js/cytoscape-entry.js`:

```javascript
// Entry esbuild dla strony eksploratora powiązań autorów.
// Buduje osobny bundle (dist/cytoscape-bundle.js) ładowany TYLKO na stronie
// grafu, żeby nie obciążać globalnego dist/bundle.js (~1.5 MB Cytoscape).
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";

cytoscape.use(fcose);
window.cytoscape = cytoscape;
```

- [ ] **Step 3: Dodaj krok esbuild w `Gruntfile.js`**

W obiekcie `shell: { ... }`, po zadaniu `esbuild` (po linii ~227),
dodaj nowe zadanie:

```javascript
            esbuildCytoscape: {
                command: 'npx esbuild src/bpp/static/bpp/js/cytoscape-entry.js ' +
                         '--bundle --minify-syntax --minify-whitespace --sourcemap ' +
                         '--outfile=src/bpp/static/bpp/js/dist/cytoscape-bundle.js ' +
                         '--format=iife --target=es2018'
            },
```

- [ ] **Step 4: Dołącz krok do tasków build**

W `grunt.registerTask('build', [...])` (linia ~248) dodaj `'shell:esbuildCytoscape',`
po `'shell:esbuild',`. To samo w `grunt.registerTask('build-non-interactive', [...])`
(linia ~255). Wynikowo (build):

```javascript
    grunt.registerTask('build', [
        'concurrent:themes',
        'shell:linkSitePackages',
        'shell:esbuild',
        'shell:esbuildCytoscape',
        'shell:patchBundle',
        'shell:collectstatic'
    ]);
    grunt.registerTask('build-non-interactive', [
        'concurrent:themes',
        'shell:linkSitePackages',
        'shell:esbuild',
        'shell:esbuildCytoscape',
        'shell:patchBundle'
    ]);
```

- [ ] **Step 5: Zbuduj bundle i zweryfikuj wynik**

Run: `npx esbuild src/bpp/static/bpp/js/cytoscape-entry.js --bundle --minify-syntax --minify-whitespace --outfile=src/bpp/static/bpp/js/dist/cytoscape-bundle.js --format=iife --target=es2018 && ls -la src/bpp/static/bpp/js/dist/cytoscape-bundle.js`
Expected: plik `cytoscape-bundle.js` powstaje (kilkaset KB), bez błędów esbuild.

- [ ] **Step 6: Commit**

```bash
git add package.json yarn.lock src/bpp/static/bpp/js/cytoscape-entry.js Gruntfile.js
git commit -m "build(frontend): osobny lazy bundle Cytoscape.js + fcose

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Uwaga: `src/bpp/static/bpp/js/dist/bundle.js` jest generowany przy buildzie —
sprawdź `.gitignore`, czy `dist/` jest ignorowany. Jeśli tak, nie commituj
`cytoscape-bundle.js` (powstaje na buildzie). Jeśli `dist/` jest w gicie,
dodaj też zbudowany plik.

---

### Task 7: Moduł JS eksploratora + finalizacja strony

**Files:**
- Create: `src/bpp/static/bpp/js/visualizations/powiazania-autorow.js`

- [ ] **Step 1: Napisz moduł eksploratora**

Utwórz `src/bpp/static/bpp/js/visualizations/powiazania-autorow.js`:

```javascript
// Eksplorator sieci współautorstwa — Cytoscape.js + fcose.
// Dane z endpointu bpp:browse_autor_powiazania_dane (per autor). Klik w węzeł
// dociąga jego współautorów i animowanie rozrasta sieć. Suwak top-N steruje
// liczbą sąsiadów rysowanych na rozwinięcie (filtr po stronie klienta).
(function () {
    "use strict";

    function init() {
        var container = document.getElementById("cytoscape-container");
        if (!container) {
            return;
        }
        if (typeof cytoscape === "undefined") {
            console.error("Cytoscape.js nie został załadowany.");
            return;
        }

        var autorId = String(container.dataset.autorId);
        var urlTemplate = container.dataset.daneUrlTemplate; // .../autor/0/powiazania/dane.json
        var emptyEl = document.getElementById("graf-empty");
        var tooltip = document.getElementById("graf-tooltip");
        var panel = document.getElementById("graf-panel");
        var slider = document.getElementById("graf-topn");
        var sliderLabel = document.getElementById("graf-topn-label");

        var topN = parseInt(slider.value, 10);
        var expanded = {};        // id -> true (węzeł rozwinięty)
        var neighborsCache = {};  // id -> [{id,label,url,shared}, ...]
        var labelCache = {};      // id -> label
        var urlCache = {};        // id -> url

        var cy = cytoscape({
            container: container,
            minZoom: 0.1,
            maxZoom: 4,
            wheelSensitivity: 0.2,
            style: [
                {
                    selector: "node",
                    style: {
                        "label": "data(label)",
                        "background-color": "#4A90E2",
                        "width": "mapData(degree, 1, 30, 18, 64)",
                        "height": "mapData(degree, 1, 30, 18, 64)",
                        "font-size": 10,
                        "color": "#222",
                        "text-valign": "bottom",
                        "text-halign": "center",
                        "text-margin-y": 3,
                        "min-zoomed-font-size": 7
                    }
                },
                {
                    selector: "node.centrum",
                    style: { "background-color": "#FF6B6B", "font-weight": "bold" }
                },
                {
                    selector: "node.rozwiniety",
                    style: { "border-width": 2, "border-color": "#2c6cb0" }
                },
                {
                    selector: "edge",
                    style: {
                        "width": "mapData(shared, 1, 20, 1, 9)",
                        "line-color": "#bbb",
                        "curve-style": "haystack",
                        "opacity": 0.55
                    }
                }
            ]
        });

        function daneUrl(id) {
            return urlTemplate.replace("/0/", "/" + id + "/");
        }

        function zapamietaj(node) {
            labelCache[node.id] = node.label;
            urlCache[node.id] = node.url;
        }

        function uruchomLayout() {
            cy.layout({
                name: "fcose",
                animate: true,
                animationDuration: 600,
                randomize: false,
                fit: true,
                padding: 40
            }).run();
        }

        function dodajWezel(id, label, url, isCentrum) {
            id = String(id);
            if (cy.getElementById(id).nonempty()) {
                return;
            }
            cy.add({
                group: "nodes",
                data: { id: id, label: label, url: url, degree: 1 },
                classes: isCentrum ? "centrum" : ""
            });
        }

        function dodajKrawedz(zrodloId, n) {
            var lo = Math.min(Number(zrodloId), Number(n.id));
            var hi = Math.max(Number(zrodloId), Number(n.id));
            var eid = "e" + lo + "_" + hi;
            if (cy.getElementById(eid).nonempty()) {
                return;
            }
            cy.add({
                group: "edges",
                data: {
                    id: eid,
                    source: String(zrodloId),
                    target: String(n.id),
                    shared: n.shared
                }
            });
        }

        function odswiezStopnie() {
            cy.batch(function () {
                cy.nodes().forEach(function (node) {
                    node.data("degree", node.degree());
                });
            });
        }

        function pokazSasiadow(id, neighbors) {
            neighbors.slice(0, topN).forEach(function (n) {
                zapamietaj(n);
                dodajWezel(n.id, n.label, n.url, false);
                dodajKrawedz(id, n);
            });
            odswiezStopnie();
        }

        function rozwin(id) {
            id = String(id);
            if (expanded[id]) {
                return;
            }
            expanded[id] = true;
            cy.getElementById(id).addClass("rozwiniety");

            if (neighborsCache[id]) {
                pokazSasiadow(id, neighborsCache[id]);
                uruchomLayout();
                return;
            }
            fetch(daneUrl(id))
                .then(function (r) {
                    if (!r.ok) { throw new Error("HTTP " + r.status); }
                    return r.json();
                })
                .then(function (data) {
                    neighborsCache[id] = data.neighbors;
                    zapamietaj(data.center);
                    pokazSasiadow(id, data.neighbors);
                    uruchomLayout();
                })
                .catch(function (e) {
                    panel.innerHTML = "Błąd pobierania danych: " + e.message;
                    panel.style.display = "block";
                });
        }

        function przebuduj() {
            cy.elements().remove();
            dodajWezel(
                autorId,
                labelCache[autorId] || container.dataset.autorLabel,
                urlCache[autorId] || "#",
                true
            );
            cy.getElementById(autorId).addClass("rozwiniety");
            pokazSasiadow(autorId, neighborsCache[autorId] || []);
            Object.keys(expanded).forEach(function (id) {
                if (id !== autorId && neighborsCache[id]) {
                    dodajWezel(id, labelCache[id] || id, urlCache[id] || "#", false);
                    cy.getElementById(id).addClass("rozwiniety");
                    pokazSasiadow(id, neighborsCache[id]);
                }
            });
            uruchomLayout();
        }

        // --- start: centrum + jego sąsiedzi ---
        fetch(daneUrl(autorId))
            .then(function (r) {
                if (!r.ok) { throw new Error("HTTP " + r.status); }
                return r.json();
            })
            .then(function (data) {
                zapamietaj(data.center);
                if (!data.neighbors.length) {
                    container.style.display = "none";
                    if (emptyEl) { emptyEl.style.display = "block"; }
                    return;
                }
                neighborsCache[autorId] = data.neighbors;
                expanded[autorId] = true;
                dodajWezel(data.center.id, data.center.label, data.center.url, true);
                cy.getElementById(autorId).addClass("rozwiniety");
                pokazSasiadow(autorId, data.neighbors);
                uruchomLayout();
            })
            .catch(function (e) {
                if (emptyEl) {
                    emptyEl.textContent = "Błąd: " + e.message;
                    emptyEl.style.display = "block";
                }
            });

        // --- hover -> tooltip ---
        cy.on("mouseover", "node", function (evt) {
            tooltip.innerHTML = "<strong>" + evt.target.data("label") + "</strong>";
            tooltip.style.display = "block";
        });
        cy.on("mousemove", function (evt) {
            var pos = evt.renderedPosition || { x: 0, y: 0 };
            tooltip.style.left = (pos.x + 14) + "px";
            tooltip.style.top = (pos.y + 14) + "px";
        });
        cy.on("mouseout", "node", function () {
            tooltip.style.display = "none";
        });

        // --- klik -> rozwiń + panel z linkiem ---
        cy.on("tap", "node", function (evt) {
            var n = evt.target;
            rozwin(n.id());
            panel.innerHTML =
                "<strong>" + n.data("label") + "</strong><br>" +
                '<a href="' + n.data("url") + '">Przejdź do strony autora →</a>';
            panel.style.display = "block";
        });

        // --- suwak top-N -> przebuduj z cache ---
        slider.addEventListener("input", function () {
            topN = parseInt(slider.value, 10);
            if (sliderLabel) { sliderLabel.textContent = topN; }
            przebuduj();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
```

- [ ] **Step 2: Zbuduj frontend**

Run: `grunt build-non-interactive`
Expected: build przechodzi, `dist/cytoscape-bundle.js` aktualny, brak błędów.

- [ ] **Step 3: Weryfikacja manualna (run-site)**

Run: `uv run run-site run --no-browser` (w tle), potem otwórz
`/bpp/autor/<pk>/powiazania/` dla autora mającego powiązania.
Sprawdź ręcznie:
- graf renderuje centrum (czerwone) + współautorów,
- hover pokazuje tooltip z nazwą,
- klik w współautora animowanie dorzuca jego współautorów,
- suwak top-N zmienia liczbę widocznych węzłów,
- panel pokazuje link „Przejdź do strony autora",
- autor bez powiązań → komunikat „Brak zarejestrowanych powiązań".

Jeśli `AuthorConnection` jest pusta lokalnie:
`uv run python src/manage.py shell -c "from powiazania_autorow.core import calculate_author_connections; calculate_author_connections()"`

- [ ] **Step 4: Lint/format**

Run: `ruff format . && ruff check src/powiazania_autorow/ src/bpp/views/browse.py`
Expected: bez błędów (lub napraw ręcznie wg wytycznych — Edit, nie `--fix`).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/static/bpp/js/visualizations/powiazania-autorow.js
git commit -m "feat(powiazania_autorow): interaktywny eksplorator sieci (Cytoscape + fcose)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Pełny przebieg testów + finalizacja

- [ ] **Step 1: Testy całej apki + dotkniętego browse**

Run: `uv run pytest src/powiazania_autorow/ -q`
Expected: PASS (wszystkie: model/core/tasks + nowe endpoint/strona/kontekst/celerybeat).

- [ ] **Step 2: System check + brak dryfu migracji**

Run: `uv run python src/manage.py check && uv run python src/manage.py makemigrations --check --dry-run`
Expected: brak problemów; brak nowych migracji (model nietknięty).

- [ ] **Step 3: pre-commit na zmienionych plikach**

Run: `pre-commit`
Expected: PASS (napraw ręcznie ewentualne uwagi — Edit, bez batch-fix).

- [ ] **Step 4: (opcjonalnie) push + PR**

Po akceptacji użytkownika:
```bash
git push -u origin powiazania-autorow-eksplorator
```

---

## Self-Review (autor planu)

**Pokrycie spec:**
- A. Sprzątanie → Task 1. ✓
- B. Endpoint danych → Task 2 (+ trasy). ✓
- C. Harmonogram → Task 5. ✓
- D. Frontend eksplorator (Cytoscape+fcose, hover/klik/expand/suwak, lazy bundle) → Task 6 (bundle) + Task 7 (logika) + Task 3 (szablon). ✓
- E. Podpięcie na stronie autora (kontekst + przycisk) → Task 4. ✓
- F. Stany brzegowe (pusty, błąd, dedup, pokazuj) → endpoint (Task 2) + JS (Task 7) + szablon empty-state (Task 3). ✓
- G. Testy backendu, Playwright pominięty → Task 2/3/4/5 testy; brak Playwright. ✓

**Spójność typów/nazw:**
- URL names: `browse_autor_powiazania`, `browse_autor_powiazania_dane` — spójnie w widokach, urls, szablonach, testach. ✓
- Widoki: `GrafPowiazanView`, `GrafPowiazanDaneView` — spójnie. ✓
- JSON: `center{id,label,url}`, `neighbors[{id,label,url,shared}]` — endpoint produkuje, JS konsumuje te same klucze. ✓
- DOM id: `cytoscape-container`, `graf-topn`, `graf-topn-label`, `graf-tooltip`, `graf-panel`, `graf-empty` — spójne szablon↔JS. ✓
- Atrybuty data: `data-autor-id`, `data-autor-label`, `data-dane-url-template` — spójne szablon↔JS. ✓

**Placeholdery:** brak — każdy krok ma realny kod/komendę.

**Ryzyka odnotowane w planie:** `.gitignore` na `dist/` (Task 6 Step 6); pusta tabela `AuthorConnection` lokalnie (Task 7 Step 3); ewentualny istniejący import `Q` w browse.py (Task 4 Step 3).
