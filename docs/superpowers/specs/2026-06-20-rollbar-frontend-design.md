# Wpięcie Rollbara we front-end (client-side error monitoring)

Data: 2026-06-20
Status: zaakceptowany (design), przed implementacją
Branch: `feat/rollbar-frontend`

## Cel

BPP ma już monitoring błędów Rollbar po stronie **backendu**
(`CustomRollbarNotifierMiddleware`, `ROLLBAR` w `settings/base.py`,
token `post_server_item` w `ROLLBAR_ACCESS_TOKEN`). Brakuje raportowania
błędów **JavaScriptu w przeglądarce** — niewyłapane wyjątki i odrzucone
promisy po stronie klienta nie trafiają nigdzie (przykład z życia:
FreshDesk #378, gdzie zapis formularza padał po cichu na 403, a użytkownik
widział tylko alert).

Ten dokument opisuje wpięcie oficjalnego klienta `rollbar.js` we front-end
tak, by błędy JS trafiały do tego samego projektu Rollbar co błędy backendu
i dało się je korelować po `environment` i `code_version`.

## Decyzje (zatwierdzone)

- **Person tracking: BRAK.** Do zdarzeń NIE dołączamy żadnych danych
  użytkownika (ani `id`, ani loginu). Same błędy techniczne. Minimalizacja
  PII.
- **Zgoda na cookie: BEZ gejtowania.** Snippet ładuje się zawsze, gdy token
  jest ustawiony — niezależnie od bannera cookie. Uzasadnienie: `rollbar.js`
  nie ustawia ciasteczek, a monitoring błędów to uzasadniony interes (nie
  tracking reklamowy/analityczny). Dodatkowo błędy najczęściej występują
  PRZED interakcją z bannerem.

## Architektura

Wzorzec skopiowany 1:1 z istniejącego `google_analytics` (context processor
warunkowo renderujący zewnętrzny snippet JS na podstawie tokenu z settings).

### 1. Settings — `src/django_bpp/settings/base.py`

- Nowa zmienna środowiskowa w deklaracji `env(...)`:
  `ROLLBAR_CLIENT_ACCESS_TOKEN=(str, "")`.
- Przy bloku `ROLLBAR`:
  `ROLLBAR_CLIENT_ACCESS_TOKEN = env("ROLLBAR_CLIENT_ACCESS_TOKEN")`.
- To token typu **`post_client_item`** — z założenia ujawniany w przeglądarce
  (potrafi wyłącznie tworzyć zdarzenia). NIE jest to sekretny token serwerowy
  `ROLLBAR_ACCESS_TOKEN` — tego NIGDY nie wolno renderować client-side.
- Domyślnie pusty → integracja jest no-opem (bezpieczne w dev i gdy token
  nie został skonfigurowany).
- `environment` i `code_version` NIE są tu duplikowane — context processor
  czyta je z istniejącego słownika `settings.ROLLBAR`, dzięki czemu override
  z `production.py` (`ROLLBAR["environment"] = "production"` / `"staging"`)
  oraz `VERSION` automatycznie się propagują i są spójne z backendem.

### 2. Context processor — `src/bpp/context_processors/rollbar.py`

```python
from django.conf import settings


def rollbar_client(request):
    """Zwraca konfigurację frontendowego Rollbara, gdy ustawiony jest
    publiczny token klienta (post_client_item). Bez tokenu — no-op."""
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

- Brak klucza `person` — realizuje decyzję „bez danych użytkownika".
- Rejestrowany w `TEMPLATES[...]["OPTIONS"]["context_processors"]` w
  `base.py`, obok `bpp.context_processors.google_analytics.google_analytics`.

### 3. Snippet — `src/django_bpp/templates/rollbar.html`

Oficjalny snippet `rollbar.js`, ale biblioteka **hostowana lokalnie** (NIE
z CDN). `rollbar.umd.min.js` pochodzi z pakietu npm `rollbar` i ląduje w
static BPP; snippet używa swojego loadera z URL-em wskazującym na
`{% static 'rollbar/rollbar.umd.min.js' %}`, dzięki czemu zachowane jest
przechwytywanie błędów z czasu ładowania strony (shim kolejkuje wywołania,
zanim pełna biblioteka się załaduje).

Mechanizm dostarczenia pliku do static (do rozstrzygnięcia w planie, preferowane
pierwsze):
- dodać `rollbar` do `package.json` (devDependency) + krok kopiujący
  `node_modules/rollbar/dist/rollbar.umd.min.js` do
  `src/django_bpp/static/rollbar/` w buildzie (Grunt) — spójne z zarządzaniem
  zależnościami front-endu; albo
- zacommitować zvendorowany plik bezpośrednio w static (prościej, ale aktualizacja
  wersji ręczna).

Konfiguracja `_rollbarConfig`:

- `accessToken: '{{ ROLLBAR_CLIENT.accessToken }}'`
- `captureUncaught: true`
- `captureUnhandledRejections: true`
- `payload.environment: '{{ ROLLBAR_CLIENT.environment }}'`
- `payload.client.javascript.code_version: '{{ ROLLBAR_CLIENT.codeVersion }}'`
- `payload.client.javascript.source_map_enabled: true`
- BEZ bloku `person`.

### 4. `src/django_bpp/templates/base.html`

Include możliwie **wcześnie w `<head>`** (przed `bundle.js` i innym JS-em
aplikacji), żeby złapać też błędy z czasu ładowania strony:

```django
{% if ROLLBAR_CLIENT %}
    {% include "rollbar.html" %}
{% endif %}
```

- NIE wewnątrz bloku `{% if cookielaw.accepted %}`.
- NIE cache'owane za zgodą — działa bezwarunkowo, gdy token obecny.

### 5. Source mapy (de-minifikacja stack trace'ów) — W ZAKRESIE

Build już emituje `bundle.js.map` i `cytoscape-bundle.js.map` (esbuild
`--sourcemap`, `Gruntfile.js`). Brakuje: (a) konfiguracji klienta pod
multi-host i (b) uploadu map do Rollbara przy release.

**a) Klient (`rollbar.html`) — wzorzec `dynamichost`.** BPP jest multi-hosted:
ten sam `bundle.js` jest serwowany z wielu domen tenantów
(`https://<tenant>/static/bpp/js/dist/bundle.js`), więc `minified_url` różni
się per deployment. Rozwiązanie rekomendowane przez Rollbara:
- w configu klienta dodać `transform`, który w każdej ramce stack trace'a
  podmienia realny host na stały token `http://dynamichost`,
- ustawić `payload.client.javascript.source_map_enabled: true` oraz
  `code_version: '{{ ROLLBAR_CLIENT.codeVersion }}'`.
Dzięki temu JEDNA wgrana mapa pasuje do wszystkich tenantów.

**b) Upload map przy release (CI, tylko master).** Krok w pipelinie buildu
obrazów POST-uje każdą mapę do `https://api.rollbar.com/api/1/sourcemap`:
- `access_token` — token **serwerowy** (`post_server_item`), wymaga scope do
  uploadu source map; w CI jako NOWY sekret GitHub Actions (np.
  `ROLLBAR_SERVER_ACCESS_TOKEN`). To NIE jest token kliencki.
- `version` — **musi** równać się `VERSION` z `src/django_bpp/version.py` (to,
  co klient raportuje jako `code_version`). Niespójność = brak dopasowania mapy.
- `minified_url` — `http://dynamichost/static/bpp/js/dist/bundle.js` (oraz
  analogicznie dla `cytoscape-bundle.js`).
- `source_map` — plik `.map`.

**Otwarte pytanie do rozstrzygnięcia w planie:** skąd CI bierze pliki `.map`
do uploadu. `make assets` biegnie w build-stage Dockera, więc mapy powstają
WEWNĄTRZ obrazu, nie na runnerze. Opcje: (1) dedykowany job CI robiący `npm ci`
+ build bundla na runnerze i upload (prościej, duplikuje build JS), albo
(2) ekstrakcja `.map` z gotowego obrazu (`docker cp`) i upload (DRY, więcej
plumbingu docker). Sekrety NIE mogą trafić do build-stage obrazu — upload
zawsze z poziomu joba CI z dostępem do sekretu.

## Testy (TDD)

Plik: `src/bpp/tests/test_rollbar_frontend.py` — wzorowany na istniejącym
`src/bpp/tests/test_google_analytics.py` (bezpośredni precedens: test context
processora + renderu snippetu z tokenem z settings, z użyciem
`override_settings`).

1. **Context processor — brak tokenu:** `rollbar_client(request)` zwraca `{}`,
   gdy `ROLLBAR_CLIENT_ACCESS_TOKEN` jest pusty.
2. **Context processor — token ustawiony:** zwraca dict z `accessToken`,
   `environment`, `codeVersion` (override przez `settings`).
3. **Render — token ustawiony:** strona front-endu zawiera snippet Rollbara,
   `accessToken` i `environment`.
4. **Render — brak tokenu:** snippet NIEobecny.
5. **Privacy lock:** wyrenderowany snippet NIE zawiera `person` ani loginu
   użytkownika (blokada regresji decyzji „bez PII").
6. **Source map / multi-host:** snippet zawiera `transform` z `dynamichost`
   oraz `source_map_enabled: true` i `code_version` równy `VERSION`.
7. **Spójność wersji:** `code_version` renderowany w snippecie == `VERSION`
   z `django_bpp.version` (ta sama wartość, którą CI poda jako `version` przy
   uploadzie mapy). Blokuje rozjazd klient↔mapa.

Upload map w CI to skrypt shellowy + wywołanie API — testowany manualnie/przez
dry-run (poza pytest); w planie opisać weryfikację (np. `--dry-run`/echo URL).

## Dokumentacja / konfiguracja

- Dopisać nową zmienną `ROLLBAR_CLIENT_ACCESS_TOKEN` do `.env.example`
  (z pustą wartością + komentarzem, że to publiczny token `post_client_item`,
  inny niż sekretny `ROLLBAR_ACCESS_TOKEN`). Użytkownik wypełnia wartość sam —
  nigdy nie trafia ona do gita.

## Zakres (YAGNI)

**W zakresie:**
- Globalne przechwytywanie `uncaught` + `unhandledrejection`.
- `environment` + `code_version` spójne z backendem.
- Gejtowane obecnością tokenu, bez PII.
- Biblioteka `rollbar.js` hostowana lokalnie (static, nie CDN).
- Source mapy: konfiguracja klienta `dynamichost` (multi-host) + upload map
  do Rollbara przy release (CI, master) z `version == VERSION`.

**Poza zakresem (przyszłe, osobne):**
- Ręczna instrumentacja konkretnych przepływów (np. zgłaszanie błędu AJAX
  zapisu formularza multiseek jako `rollbar.error(...)`).
- Person tracking (gdyby kiedyś zdecydowano inaczej).

## Ryzyka / uwagi

- **Pomyłka tokenów:** krytyczne, by w `rollbar.html` trafił token
  `post_client_item`, nie sekretny `post_server_item`. Realizowane przez
  osobną zmienną `ROLLBAR_CLIENT_ACCESS_TOKEN`.
- **CSP:** biblioteka hostowana lokalnie ze static (same-origin), więc nie
  wymaga dopuszczania zewnętrznego CDN w `script-src`. Zdarzenia POST-owane są
  do `api.rollbar.com` — jeśli istnieje polityka CSP `connect-src`, dopisać tam
  domenę Rollbara. Zweryfikować przy implementacji.
- **Source mapy — DECYZJA UŻYTKOWNIKA (patrz niżej).** Build już emituje
  `bundle.js.map` (esbuild `--sourcemap`, `Gruntfile.js`). Bez kroku uploadu
  mapy do Rollbara stack trace'y w panelu pozostaną zminifikowane (czytelne
  „że błąd jest", mniej „w której linii źródła").
