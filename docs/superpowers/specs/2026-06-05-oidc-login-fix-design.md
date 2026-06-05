# OIDC: naprawa logowania + menu „logowanie instytucjonalne"

Data: 2026-06-05
Branch: `feature/oidc-login` → PR do `feature/multi-hosted-config`

## Problem

Logowanie OIDC (Keycloak, realm KA) nie działa. Z logów:

1. **„Claims verification failed"** — `mozilla_django_oidc.verify_claims`
   sprawdza `"email" in claims`, bo scope zawiera `email`. Keycloak wysyła
   klucz **`mail`**, nie `email`. Poprawne logowanie jest odrzucane.
   Te same `filter_users_by_claims` (dopasowanie po e-mailu) i `create_user`
   czytają `email`, więc nawet po przejściu konto miałoby pusty e-mail.

2. **`KeyError: 'username'`** — przy nieudanym logowaniu Django wysyła sygnał
   `user_login_failed`, a handler `easyaudit` robi twardy `credentials['username']`
   (a nie `.get(...)`). Callback mozilli woła `auth.authenticate(request,
   nonce=…, code_verifier=…)` — bez `username`. Przy
   `DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS = True` ten `KeyError` wybucha jako
   HTTP 500. Uwaga: `credentials` to NIE są claimy — w tym miejscu
   `preferred_username` fizycznie nie istnieje (claimy pobierane są dopiero
   wewnątrz backendu).

3. **Brak menu** — OIDC istnieje dziś tylko jako przycisk pod formularzem
   logowania (`registration/login.html`). User chce parytetu z Microsoftem:
   w menu „logowanie instytucjonalne" (→ OIDC) i „logowanie BPP" (→ lokalne),
   bez formularza z przyciskiem pod spodem.

## Decyzje (potwierdzone z userem)

- Dopasowanie/tworzenie konta **po e-mailu** (`mail`→`email`); `username` z
  `preferred_username` (→ `email` → `sub`); imię/nazwisko z
  `given_name`/`family_name`. **Bez** `person_id`.
- Domyślne logowanie **jak Microsoft**: `login_form` → redirect na OIDC;
  „logowanie BPP" osobno w menu (`local_login_form`).
- **Gating bez zmian**: każdy z realmu dostaje zwykłe konto bez `is_staff`.
- Banner `[OIDC]` z claimami: ścisz do `logger.debug` (koniec stderr).

## Rozwiązanie

### 1. Normalizacja claimów — `src/oidc_integration/backends.py`
- Nadpisać `get_userinfo()`: jeśli brak `email`, a jest `mail`, ustaw
  `claims["email"] = claims["mail"]`. Jeden chokepoint — `verify_claims`,
  `filter_users_by_claims` (domyślny) i `create_user` dostają znormalizowany
  słownik.
- `create_user` bez zmian merytorycznych (username `preferred_username`→
  `email`→`sub`, imię/nazwisko z claimów) — teraz z niepustym e-mailem.
- `_dump_claims_to_stderr` → `logger.debug` (bez bannera na stderr).

### 2. Odporność easyaudit — `src/oidc_integration/apps.py` (+ moduł compat)
- W `AppConfig.ready()`, tylko gdy `easyaudit` zainstalowany: zaimportuj
  `easyaudit.signals.auth_signals` (gwarancja, że easyaudit już się podłączył),
  rozłącz jego `user_login_failed` (`dispatch_uid="easy_audit_signals_login_failed"`),
  podłącz cienki wrapper z tym samym `dispatch_uid`.
- Wrapper: jeśli w `credentials` brak `USERNAME_FIELD`, dołóż go
  (`credentials.get("preferred_username")` lub `""`), a potem **deleguj do
  oryginalnej funkcji easyaudit** (reużycie logiki audytu; brak duplikacji,
  odporne na wersje). Efekt: nieudane logowanie OAuth jest audytowane czysto,
  bez 500. Bez własnego widoku callbacka, bez `except KeyError`.

### 3. Menu + routing — `top_bar.html`, `django_bpp/urls.py`, `registration/login.html`
- `urls.py`: nowa gałąź gdy OIDC włączone (a Microsoft nie) — lustro gałęzi
  Microsoftu: `local_login_form` (formularz BPP), `login_form` →
  `RedirectView(pattern_name="oidc_authentication_init", query_string=True)`,
  `logout` = `BppOIDCAwareLogoutView`.
- `top_bar.html`: warunek `microsoft_login_enabled` → `microsoft_login_enabled
  or oidc_login_enabled`; „logowanie instytucjonalne" celuje w
  `bpp:microsoft_auth_redirect` albo `oidc_authentication_init` zależnie od
  tego, co włączone; „logowanie BPP" → `local_login_form`.
- `registration/login.html`: usunąć przycisk OIDC spod formularza.

### 4. Testy (TDD)
- backend: `get_userinfo` normalizuje `mail`→`email`; `verify_claims`
  przechodzi z `mail`; `create_user` bierze username z `preferred_username`,
  e-mail z `mail`, ustawia imię/nazwisko; re-login dopasowuje po e-mailu.
- easyaudit compat: wrapper dokłada brakujący `username` i deleguje; przy
  obecnym `username` nie rusza credentials.
- urls/settings: w trybie OIDC istnieje `local_login_form`, a `login_form`
  redirectuje na OIDC.

## Poza zakresem
- Powiązanie konta z `Autor` (po `person_id` czy inaczej).
- Gating po rolach/grupach Keycloaka.
- Mapowanie ról → grupy/uprawnienia.
