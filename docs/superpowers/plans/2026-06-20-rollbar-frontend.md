# Rollbar front-end (client-side error monitoring) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wpiąć klienta `rollbar.js` we front-end BPP, tak by niewyłapane błędy JS i odrzucone promisy trafiały do tego samego projektu Rollbar co błędy backendu.

**Architecture:** Wzorzec skopiowany z istniejącego `google_analytics`: context processor warunkowo (gdy ustawiony publiczny token `post_client_item`) udostępnia konfigurację szablonowi; snippet ładowany wcześnie w `<head>` w `base.html`. Biblioteka hostowana lokalnie ze static (npm + Grunt copy), bez CDN. Bez danych użytkownika (PII) i bez gejtowania zgodą cookie.

**Tech Stack:** Django (settings + context processor + template), `django-environ` (env vars), npm + Grunt (`grunt-shell`) + esbuild (frontend), pytest (`override_settings`, `RequestFactory`).

## Global Constraints

- Max długość linii: 88 znaków (ruff).
- Python: `uv run` przed KAŻDą komendą Pythona/pytest. Nigdy goły `python`.
- Token w szablonie to `post_client_item` (publiczny). NIGDY nie renderować client-side sekretnego `ROLLBAR["access_token"]` (`post_server_item`).
- Bez PII: snippet NIE zawiera bloku `person` ani loginu użytkownika.
- Bez gejtowania zgodą cookie: snippet poza blokiem `{% if cookielaw.accepted %}`, nie cache'owany.
- Komentarze w szablonach Django `{# ... #}` — każda linia z własnym `{#` i `#}`.
- Pusty token (`ROLLBAR_CLIENT_ACCESS_TOKEN=""`) → integracja jest no-opem (domyślnie wyłączona).
- Spójność: `code_version` w kliencie == `VERSION` z `django_bpp.version`.
- Source mapy SĄ POZA ZAKRESEM (osobny PR). Tu tylko `source_map_enabled: false`.

---

## File Structure

- `src/django_bpp/settings/base.py` (modify) — deklaracja env var, ustawienie `ROLLBAR_CLIENT_ACCESS_TOKEN`, rejestracja context processora.
- `src/bpp/context_processors/rollbar.py` (create) — `rollbar_client(request)`.
- `src/django_bpp/templates/rollbar.html` (create) — snippet inicjalizujący Rollbara.
- `src/django_bpp/templates/base.html` (modify) — include snippetu wcześnie w `<head>`.
- `package.json` (modify) — `rollbar` jako devDependency.
- `Gruntfile.js` (modify) — task kopiujący `rollbar.umd.min.js` do static.
- `.gitignore` (modify) — ignoruj zvendorowany plik (build artifact).
- `.env.example` (modify) — dokumentacja nowej zmiennej.
- `src/bpp/tests/test_rollbar_frontend.py` (create) — testy context processora i renderu.

---

## Task 1: Settings + context processor

**Files:**
- Modify: `src/django_bpp/settings/base.py` (env decl ~155, setting ~1440, context_processors ~289)
- Create: `src/bpp/context_processors/rollbar.py`
- Modify: `.env.example`
- Test: `src/bpp/tests/test_rollbar_frontend.py`

**Interfaces:**
- Produces: `bpp.context_processors.rollbar.rollbar_client(request) -> dict`. Zwraca `{}` gdy brak tokenu, inaczej `{"ROLLBAR_CLIENT": {"accessToken": str, "environment": str, "codeVersion": str}}`.
- Produces: setting `ROLLBAR_CLIENT_ACCESS_TOKEN: str` (domyślnie `""`).

- [ ] **Step 1: Write the failing test**

Create `src/bpp/tests/test_rollbar_frontend.py`:

```python
from django.conf import settings
from django.test import RequestFactory, override_settings

from bpp.context_processors.rollbar import rollbar_client


def test_rollbar_client_no_token_returns_empty():
    request = RequestFactory().get("/")
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN=""):
        assert rollbar_client(request) == {}


def test_rollbar_client_with_token_returns_config():
    request = RequestFactory().get("/")
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        ctx = rollbar_client(request)
    client = ctx["ROLLBAR_CLIENT"]
    assert client["accessToken"] == "post_client_abc"
    assert client["environment"] == settings.ROLLBAR["environment"]
    assert client["codeVersion"] == str(settings.ROLLBAR["code_version"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_rollbar_frontend.py -p no:randomly -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bpp.context_processors.rollbar'`.

- [ ] **Step 3: Create the context processor**

Create `src/bpp/context_processors/rollbar.py`:

```python
from django.conf import settings


def rollbar_client(request):
    """Konfiguracja frontendowego Rollbara dla szablonu.

    Zwraca dane tylko gdy ustawiony jest publiczny token klienta
    (``post_client_item``). Bez tokenu — no-op (pusty kontekst), więc
    integracja jest domyślnie wyłączona. NIE dołącza danych użytkownika.
    """
    token = getattr(settings, "ROLLBAR_CLIENT_ACCESS_TOKEN", "")
    if not token:
        return {}
    return {
        "ROLLBAR_CLIENT": {
            "accessToken": token,
            "environment": settings.ROLLBAR.get("environment", "development"),
            "codeVersion": str(settings.ROLLBAR.get("code_version", "")),
        }
    }
```

- [ ] **Step 4: Add the env var declaration in `base.py`**

In `src/django_bpp/settings/base.py`, find the env declaration:

```python
    # Rollbar access settings
    #
    ROLLBAR_ACCESS_TOKEN=(str, None),
```

Replace with:

```python
    # Rollbar access settings
    #
    ROLLBAR_ACCESS_TOKEN=(str, None),
    # Publiczny token klienta (post_client_item) do frontendowego Rollbara.
    ROLLBAR_CLIENT_ACCESS_TOKEN=(str, ""),
```

- [ ] **Step 5: Add the setting next to the ROLLBAR block in `base.py`**

Find the `ROLLBAR = {` block. Immediately AFTER its closing `}` add:

```python
# Publiczny token klienta (post_client_item) do frontendowego Rollbara.
# INNY niż sekretny ROLLBAR["access_token"] (post_server_item) — ten można
# bezpiecznie renderować w przeglądarce. Pusty = front-end Rollbar wyłączony.
ROLLBAR_CLIENT_ACCESS_TOKEN = env("ROLLBAR_CLIENT_ACCESS_TOKEN")
```

- [ ] **Step 6: Register the context processor in `base.py`**

Find in `TEMPLATES[...]["OPTIONS"]["context_processors"]`:

```python
                "bpp.context_processors.google_analytics.google_analytics",
```

Add directly below it:

```python
                "bpp.context_processors.rollbar.rollbar_client",
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_rollbar_frontend.py -p no:randomly -q`
Expected: PASS (2 passed).

- [ ] **Step 8: Document the env var in `.env.example`**

Append to `.env.example`:

```bash
# Publiczny token klienta Rollbar (post_client_item) do raportowania błędów
# front-endu. INNY niż sekretny ROLLBAR_ACCESS_TOKEN (post_server_item).
# Bezpieczny do ujawnienia w przeglądarce. Pusty = front-end Rollbar wyłączony.
ROLLBAR_CLIENT_ACCESS_TOKEN=
```

- [ ] **Step 9: Lint and commit**

Run: `uv run ruff check src/bpp/context_processors/rollbar.py src/bpp/tests/test_rollbar_frontend.py && uv run ruff format --check src/bpp/context_processors/rollbar.py src/bpp/tests/test_rollbar_frontend.py`
Expected: All checks passed / already formatted.

```bash
git add src/bpp/context_processors/rollbar.py src/django_bpp/settings/base.py \
        src/bpp/tests/test_rollbar_frontend.py .env.example
git commit -m "feat(rollbar): context processor + setting dla frontendowego Rollbara"
```

---

## Task 2: Vendor rollbar.js lokalnie (npm + Grunt copy)

**Files:**
- Modify: `package.json` (devDependencies), `package-lock.json` (auto)
- Modify: `Gruntfile.js` (`shell.copyRollbar` + listy zadań `build` / `build-non-interactive`)
- Modify: `.gitignore`

**Interfaces:**
- Produces: plik `src/bpp/static/rollbar/rollbar.umd.min.js` (build artifact, niecommitowany), serwowany jako `/static/rollbar/rollbar.umd.min.js`.

- [ ] **Step 1: Install the rollbar npm package as a devDependency**

Run: `npm install --save-dev rollbar`
Expected: `package.json` zyskuje `rollbar` w `devDependencies`, `package-lock.json` zaktualizowany, pojawia się `node_modules/rollbar/`.

- [ ] **Step 2: Verify the UMD build exists and note the global name**

Run: `ls node_modules/rollbar/dist/rollbar.umd.min.js`
Expected: ścieżka istnieje.

Run: `grep -oE '(self|global|this)\.[A-Za-z]+=[A-Za-z]+\(\)' node_modules/rollbar/dist/rollbar.umd.min.js | head`
Cel: potwierdzić nazwę globala (spodziewane `rollbar` lub `Rollbar`). Snippet w Task 3 jest defensywny (`window.Rollbar || window.rollbar`), więc obie nazwy są obsłużone — ten krok to tylko weryfikacja.

- [ ] **Step 3: Ignore the vendored build artifact in `.gitignore`**

Append to `.gitignore`:

```gitignore
# Rollbar.js kopiowany z node_modules przez grunt (build artifact, nie commitować)
src/bpp/static/rollbar/
```

- [ ] **Step 4: Add the Grunt copy task**

In `Gruntfile.js`, inside the `shell: {` config object (obok `esbuild`, `collectstatic`), add a new entry:

```javascript
            copyRollbar: {
                command: 'mkdir -p src/bpp/static/rollbar && ' +
                         'cp node_modules/rollbar/dist/rollbar.umd.min.js ' +
                         'src/bpp/static/rollbar/rollbar.umd.min.js'
            },
```

- [ ] **Step 5: Wire the task into the build sequences**

In `Gruntfile.js`, in `grunt.registerTask('build', [ ... ])`, add `'shell:copyRollbar',` directly BEFORE `'shell:collectstatic'`:

```javascript
    grunt.registerTask('build', [
        'sass',
        'shell:linkSitePackages',
        'shell:esbuild',
        'shell:esbuildCytoscape',
        'shell:esbuildThree',
        'shell:patchBundle',
        'shell:copyRollbar',
        'shell:collectstatic'
    ]);
```

In `grunt.registerTask('build-non-interactive', [ ... ])`, add `'shell:copyRollbar'` as the LAST entry:

```javascript
    grunt.registerTask('build-non-interactive', [
        'sass',
        'shell:linkSitePackages',
        'shell:esbuild',
        'shell:esbuildCytoscape',
        'shell:esbuildThree',
        'shell:patchBundle',
        'shell:copyRollbar'
    ]);
```

(Skopiuj dokładną listę istniejących wpisów `sass`/`linkSitePackages`/... z pliku — powyżej pokazany typowy układ; dodaj tylko `shell:copyRollbar`.)

- [ ] **Step 6: Run the copy task and verify the file lands in static**

Run: `npx grunt shell:copyRollbar`
Then: `ls -la src/bpp/static/rollbar/rollbar.umd.min.js`
Expected: plik istnieje (kilkadziesiąt–kilkaset KB).

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json Gruntfile.js .gitignore
git commit -m "build(rollbar): kopiuj rollbar.umd.min.js do static (npm + grunt)"
```

(Plik `src/bpp/static/rollbar/rollbar.umd.min.js` NIE jest commitowany — jest gitignorowany jak `bundle.js`.)

---

## Task 3: Snippet + include w base.html (render tests)

**Files:**
- Create: `src/django_bpp/templates/rollbar.html`
- Modify: `src/django_bpp/templates/base.html` (blok `extrahead`)
- Test: `src/bpp/tests/test_rollbar_frontend.py` (dopisać testy renderu)

**Interfaces:**
- Consumes: `ROLLBAR_CLIENT` z context processora (Task 1) — `accessToken`, `environment`, `codeVersion`.
- Consumes: `/static/rollbar/rollbar.umd.min.js` (Task 2).

- [ ] **Step 1: Write the failing render tests**

Append to `src/bpp/tests/test_rollbar_frontend.py`:

```python
import pytest


@pytest.mark.django_db
def test_rollbar_snippet_absent_without_token(client):
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN=""):
        res = client.get("/")
    assert b"_rollbarConfig" not in res.content


@pytest.mark.django_db
def test_rollbar_snippet_present_with_token(client):
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        res = client.get("/")
    assert b"_rollbarConfig" in res.content
    assert b"post_client_abc" in res.content
    assert b"rollbar/rollbar.umd.min.js" in res.content


@pytest.mark.django_db
def test_rollbar_snippet_has_no_person_data(client):
    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        res = client.get("/")
    assert b"_rollbarConfig" in res.content
    assert b"person:" not in res.content


@pytest.mark.django_db
def test_rollbar_code_version_matches_VERSION(client):
    from django_bpp.version import VERSION

    with override_settings(ROLLBAR_CLIENT_ACCESS_TOKEN="post_client_abc"):
        res = client.get("/")
    assert VERSION.encode() in res.content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/bpp/tests/test_rollbar_frontend.py -p no:randomly -q -k "snippet or code_version"`
Expected: FAIL — `_rollbarConfig` / `post_client_abc` nieobecne (brak snippetu w stronie).

- [ ] **Step 3: Create the snippet template**

Create `src/django_bpp/templates/rollbar.html`:

```django
{% load static %}
{# Rollbar front-end (client-side error monitoring). #}
{# Ładowane wcześnie w <head>, by łapać też błędy z czasu ładowania strony. #}
{# Biblioteka hostowana lokalnie ze static (nie CDN). #}
{# Bez danych użytkownika (person) i bez gejtowania zgodą cookie. #}
<script src="{% static 'rollbar/rollbar.umd.min.js' %}"></script>
<script>
    (function () {
        var _rollbarConfig = {
            accessToken: "{{ ROLLBAR_CLIENT.accessToken }}",
            captureUncaught: true,
            captureUnhandledRejections: true,
            payload: {
                environment: "{{ ROLLBAR_CLIENT.environment }}",
                client: {
                    javascript: {
                        code_version: "{{ ROLLBAR_CLIENT.codeVersion }}",
                        source_map_enabled: false
                    }
                }
            }
        };
        var ns = window.Rollbar || window.rollbar;
        if (ns && typeof ns.init === "function") {
            window.Rollbar = ns.init(_rollbarConfig);
        }
    })();
</script>
```

- [ ] **Step 4: Include the snippet early in `base.html`**

In `src/django_bpp/templates/base.html`, find the start of the `extrahead` block:

```django
{% block extrahead %}
    {{ block.super }}
```

Replace with (include BEFORE `block.super`, tak by Rollbar ładował się najwcześniej):

```django
{% block extrahead %}
    {% if ROLLBAR_CLIENT %}
        {% include "rollbar.html" %}
    {% endif %}

    {{ block.super }}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_rollbar_frontend.py -p no:randomly -q`
Expected: PASS (6 passed — 2 z Task 1 + 4 render).

- [ ] **Step 6: Commit**

```bash
git add src/django_bpp/templates/rollbar.html src/django_bpp/templates/base.html \
        src/bpp/tests/test_rollbar_frontend.py
git commit -m "feat(rollbar): snippet front-endu w <head> base.html"
```

---

## Task 4: Weryfikacja końcowa

**Files:** brak zmian (weryfikacja).

- [ ] **Step 1: Full new-test run on a fresh container**

Run: `uv run pytest src/bpp/tests/test_rollbar_frontend.py -p no:randomly -q`
Expected: 6 passed.

- [ ] **Step 2: Smoke — render strony z tokenem i bez (manualnie przez run-site, opcjonalnie)**

Opcjonalnie: ustaw `ROLLBAR_CLIENT_ACCESS_TOKEN` w `.env`, `uv run run-site run --no-browser`, pobierz `/` i potwierdź obecność `_rollbarConfig` oraz `<script src=".../static/rollbar/rollbar.umd.min.js">`. Bez tokenu — snippet nieobecny.

- [ ] **Step 3: Ruff na całości zmian**

Run: `uv run ruff check src/bpp/context_processors/rollbar.py src/bpp/tests/test_rollbar_frontend.py src/django_bpp/settings/base.py`
Expected: All checks passed.

- [ ] **Step 4: (Po review) push + PR do dev**

```bash
git push -u origin feat/rollbar-frontend
gh pr create --base dev --title "feat: Rollbar front-end (client-side error monitoring)" --body "<opis: zakres kliencki, bez PII, bez gejtowania cookie, source mapy w follow-upie>"
```

---

## Self-Review (wypełnione przy pisaniu planu)

- **Pokrycie specu:** settings+CP (Task 1), lokalny hosting npm+grunt (Task 2), snippet+base.html (Task 3), .env.example (Task 1/Step 8), testy 1–6 (Task 1+3). Source mapy świadomie poza zakresem (zgodnie ze specem). ✔
- **Placeholdery:** brak — cały kod podany wprost. ✔
- **Spójność nazw:** `rollbar_client`, `ROLLBAR_CLIENT`, `ROLLBAR_CLIENT_ACCESS_TOKEN`, `rollbar/rollbar.umd.min.js`, `_rollbarConfig` użyte spójnie we wszystkich taskach. ✔
