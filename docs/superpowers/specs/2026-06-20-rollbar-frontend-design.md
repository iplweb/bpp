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

Oficjalny snippet `rollbar.js` (async-load `rollbar.min.js` z CDN Rollbara —
ta sama metoda „zewnętrzny skrypt z CDN" co snippet GA), skonfigurowany:

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

**Poza zakresem (przyszłe, osobne):**
- Ręczna instrumentacja konkretnych przepływów (np. zgłaszanie błędu AJAX
  zapisu formularza multiseek jako `rollbar.error(...)`).
- Upload source map do Rollbara (de-minifikacja stack trace'ów).
- Person tracking (gdyby kiedyś zdecydowano inaczej).

## Ryzyka / uwagi

- **Pomyłka tokenów:** krytyczne, by w `rollbar.html` trafił token
  `post_client_item`, nie sekretny `post_server_item`. Realizowane przez
  osobną zmienną `ROLLBAR_CLIENT_ACCESS_TOKEN`.
- **CSP:** snippet ładuje skrypt z CDN Rollbara. BPP już ładuje GA z CDN
  googletagmanager, więc zewnętrzne skrypty są dopuszczone — brak dodatkowej
  konfiguracji CSP oczekiwany. Zweryfikować przy implementacji.
- **Bez source map** stack trace'y z `bundle.js` będą zminifikowane — czytelne
  na poziomie „że błąd jest", mniej na poziomie „w której linii źródła".
  Upload source map to świadomy follow-up poza zakresem.
