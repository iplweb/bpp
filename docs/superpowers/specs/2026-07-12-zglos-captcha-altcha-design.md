# Feature: ALTCHA (proof-of-work) na anonimowym formularzu zgłoszeń

Data: 2026-07-12
Gałąź: `feat/zglos-captcha-altcha`
Kontynuacja hardeningu formularza zgłaszania publikacji (po naprawie #2 —
limity uploadu). Adresuje **tempo** anonimowych zgłoszeń (spam/DoS), którego
limity plików nie ruszały.

## Cel i decyzje (uzgodnione z właścicielem)

- **Mechanizm:** ALTCHA — proof-of-work, **self-hosted, in-process** (bez
  osobnej usługi/kontenera). GDPR-clean, WCAG 2.2 AA, zero danych do trzeciej
  strony.
- **Bramka:** tylko dla **anonimowych** (`not request.user.is_authenticated`).
  Zalogowany pracownik uczelni nie jest wektorem spamu → bez tarcia.
- **Umiejscowienie:** **pierwszy krok** kreatora (`RodzajPublikacjiForm`,
  step "0") — odrzuca bota, zanim dojdzie do uploadu plików (krok 2).
- **Docker:** żadnej nowej usługi. `ALTCHA_HMAC_KEY` to sekret env
  **auto-generowany w bpp-deploy** (`_ensure_secret`, jak inne sekrety) i
  wpięty do wszystkich serwisów Django — dzięki temu default ON nie psuje
  upgrade'ów (każda instalacja dostaje klucz automatycznie).
- **Model klucza = jak `SECRET_KEY`** (świadoma decyzja właściciela): sentinel
  default w `base.py`, placeholder w `.env.docker`, dummy inline na buildzie,
  **bez** hard import-time `raise` (który psuł build). Zamiast fail-fast —
  nie-fatalny **system-check WARNING**, gdy captcha ON a klucz to placeholder.

## Architektura ALTCHA (dlaczego bez usługi)

PoW liczy **przeglądarka** (web component ~17 kB gzip). Serwer tylko:
1. **generuje challenge** — HMAC-podpisany sekretem (`django-altcha`, in-proc),
2. **weryfikuje rozwiązanie** — in-proc, + ochrona przed replay przez Django
   cache (BPP ma Redis).

Biblioteki:
- **`django-altcha`** (PyPI, aboutcode-org, 1.0.0) — `AltchaField` + widget +
  `AltchaChallengeView`. Ustawienie `ALTCHA_HMAC_KEY`. **Sam bundluje web
  component** (`static/altcha/altcha.min.js`) → self-host bez CDN, bez npm/Grunt
  (patrz C). Zero osobnej paczki frontendowej.

## Rozwiązanie

### A. Zależności + konfiguracja

- `pyproject.toml`: dodać `django-altcha`; `INSTALLED_APPS += ["django_altcha"]`.
  **To wystarcza do self-hostu widgetu** — django-altcha 1.0.0 bundluje
  `django_altcha/static/altcha/altcha.min.js`, a `ALTCHA_JS_URL` domyślnie
  rozwiązuje się przez `static()`. `collectstatic` (kontrakt Docker build-stage)
  łapie app-static normalnie. **Żadnego npm/Grunt/`Media` override** (patrz C).
- `ALTCHA_HMAC_KEY` (sekret HMAC-signing challenge) — **odwzorowanie wzorca
  `SECRET_KEY`** (`base.py:26,107,850`: sentinel default + `env(...)`; brak
  hard-raise w `production.py`):
  - **`base.py`:** `ALTCHA_HMAC_KEY_UNSET = "Please set the ALTCHA_HMAC_KEY..."`
    (sentinel), `ALTCHA_HMAC_KEY = env("ALTCHA_HMAC_KEY", default=...UNSET)`.
    **Bez** import-time `raise` — to on psuł build (patrz niżej).
  - **`.env.docker` (dev compose):** placeholder (jak
    `DJANGO_BPP_SECRET_KEY="ZMIEN..."`). Captcha w dev compose jest dev-only.
  - **Build (`testserver` collectstatic):** `ALTCHA_HMAC_KEY=
    build-time-only-not-used` **inline w RUN-ie** — dokładnie jak istniejący
    `DJANGO_BPP_SECRET_KEY=build-time-only-not-used`. Inline env RUN-a NIE
    persystuje w obrazie → nic forgeable nie ląduje w publicznym obrazie.
  - **`local.py` (dev/run-site):** **efemeryczny** `secrets.token_hex(32)` przy
    load-zie settings (widget faktycznie działa, nic forgeable w repo).
  - **`test.py`:** stały test-key (captcha domyślnie wyłączona — niżej; klucz
    użyty przez testy captchy, które włączają ją przez `@override_settings`).
  - **Produkcja:** realny klucz **auto-generowany w bpp-deploy** (sekcja E).

  **Dlaczego bez hard-guardu:** import-time `raise ImproperlyConfigured` w
  `production.py` rozbijał trzy niezależne konsumpcje production-settings —
  build `testserver` (`collectstatic` pod `DJANGO_SETTINGS_MODULE=production`),
  dev `docker compose up` (obraz z wbakowanym production + commitowany
  `.env.docker`) oraz worker/beatserver. Repo nie stosuje takiego raise nawet
  dla `SECRET_KEY`. Zamiast tego — miękki warning (niżej) + auto-gen w prod.

- **System-check WARNING (nie-fatal):** `django.core.checks` rejestrowany w
  `AppConfig.ready()` app `zglos_publikacje`: gdy `ZGLOS_CAPTCHA_ENABLED` a
  `ALTCHA_HMAC_KEY` == sentinel/placeholder → `checks.Warning` (nie `Error`).
  Level Warning **nie wywala** `collectstatic`/`manage.py` (w odróżnieniu od
  `raise`), więc build i dev są bezpieczne; operator dostaje sygnał
  „captcha ON, a klucz to placeholder" na `manage.py check`/starcie komend.
  (Świadomie best-effort: checki nie biegną pod czystym gunicorn/daphne —
  realną gwarancję klucza w prod daje auto-gen bpp-deploy, nie ten check.)
- `ZGLOS_CAPTCHA_ENABLED` (bool): `base.py` default `True`; **`test.py`
  = `False`** (cała dotychczasowa suita `zglos_publikacje` + Playwright,
  wspólne `--ds=django_bpp.settings.test`, przechodzą bez zmian — pole ALTCHA
  w ogóle nie powstaje). W dev (`local.py`) **włączona** — świadomie, do
  oglądania w `run-site`. **`get_form_kwargs` czyta ten flag w call-time**
  (nie stała modułowa), inaczej `@override_settings` w nowych testach nie
  zadziała.
- **Replay-protection (cache):** `ALTCHA_CACHE_ALIAS` domyślnie `"default"`.
  `production.py` → Redis (działa). **Uwaga: dev/test `default` = DummyCache →
  `is_challenge_used()` zawsze `False` (replay-check to no-op).** Nowe testy
  replay MUSZĄ override'ować cache na locmem, inaczej testują nic.

### B. Bramka anon-only + pole warunkowe (unik ponownej weryfikacji)

Dlaczego flaga (SPROSTOWANIE po review): `render_done` rewaliduje WSZYSTKIE
kroki. Pole ALTCHA na kroku 0 rewalidowane ze starymi danymi (brak świeżego
PoW; do tego replay-protection ubiłby ponowne użycie) byłoby niepoprawne —
ale to **NIE** daje 500: formtools robi `render_revalidation_failure` →
**HTTP 200, powrót na krok 0** z błędem „Challenge already used"
(`AltchaField.validate` rzuca zwykły `ValidationError`, nie wyjątek jak
`FileNotFoundError` przy `pliki`). Flaga jest więc potrzebna z powodu **UX**
(inaczej user po wypełnieniu 5 kroków wraca na krok 0 i re-solve), nie 500.
Wzorzec jak `pliki_juz_zapisane`:

- `Zgloszenie_PublikacjiWizard.get_form_kwargs("0")` przekazuje
  `captcha_wymagany: bool` = `settings.ZGLOS_CAPTCHA_ENABLED` (czytane
  **call-time**) AND `not request.user.is_authenticated` AND
  NOT `request.session.get("zglos_captcha_ok")`.
- `RodzajPublikacjiForm.__init__(captcha_wymagany=False)`: dodaje `AltchaField`
  **tylko** gdy `captcha_wymagany`. Inaczej pole nieobecne. (Forma dostaje sam
  bool — nie potrzebuje całego `request`.)
- Po ważnym POST kroku 0 z zweryfikowanym ALTCHA (`AltchaField.validate`) →
  wizard ustawia `request.session["zglos_captcha_ok"] = True` w
  **`process_step` dla kroku "0"** (istniejący override obsługuje dziś tylko
  "2" — dodać branch "0"). `process_step` wykonuje się PRZED `set_step_data`
  i przed czyszczeniem cache warunków, więc flaga jest na miejscu, zanim
  cokolwiek rewaliduje krok 0.
- Rewalidacja w `render_done`: flaga ustawiona → `captcha_wymagany=False` →
  pole nieobecne → brak ponownej weryfikacji, `done()` dochodzi do skutku.
- **Flagę czyścić na POCZĄTKU `done()`** (nie na końcu) — konsekwentnie wobec
  wczesnych `raise` w `done()`; koszt = 1 PoW na 1 utworzone zgłoszenie.

**Znane, zaakceptowane ograniczenie flagi:** jedno rozwiązanie PoW odblokowuje
w tej samej sesji wielokrotny upload tmp (pętla krok 0→2→2…), bo tworzenie
rekordu jest dopiero w `done()`. PoW i tak tego nie broni (bot bierze świeżą
sesję + tani PoW/sesję) — upload-DoS pozostaje tematem **rate-limitu**, nie
CAPTCHY (sprzątanie tmp pokrywa naprawa #2 + cron co 6h).

### C. Frontend (self-host widgetu — django-altcha robi to sam)

SPROSTOWANIE po review: **żadnego npm/Grunt/`Media` override.** django-altcha
1.0.0 bundluje `django_altcha/static/altcha/altcha.min.js`, a `ALTCHA_JS_URL`
domyślnie rozwiązuje się przez `static()`. Dokładanie paczki npm tworzyłoby
DRUGĄ kopię widgetu i ryzyko version-skew (bundlowany JS musi pasować do
formatu payloadu pythonowej libki). Wystarczy:

- `INSTALLED_APPS += ["django_altcha"]` (sekcja A) + `collectstatic` (kontrakt
  Docker build-stage łapie app-static normalnie — patrz CLAUDE.md „Static files
  contract"). Zero dodatkowej roboty frontendowej.
- `AltchaField` z opcją **`challengeurl`** (nie `challengejson`) wskazującą na
  `AltchaChallengeView` django-altcha, zamontowany w `zglos_publikacje/urls.py`.
  URL przez **`reverse_lazy`** (pole definiowane przy imporcie modułu `forms`).
  Dzięki `challengeurl` działa `refetchonexpire` — challenge nie wygasa przy
  dłuższym wypełnianiu kroku 0.
- Ustawić `auto="onsubmit"` (lub `"onload"`) na widgecie, żeby po spaleniu
  challenge (np. user rozwiązał PoW, ale forma padła na innym polu kroku 0 —
  `mark_challenge_used` odpala się w `validate` niezależnie od reszty)
  re-solve był bezobsługowy.
- Szablon kroku 0 (`step_rodzaj.html`): pole renderuje `<altcha-widget>` tylko
  gdy jest obecne (anon). Ikony public-frontend = Foundation (nie dotyczy
  widgetu).
- CSP: BPP obecnie nie ustawia żadnego CSP — motywacja self-hostu jest
  prospektywna (prywatność + brak CDN). Gdyby CSP kiedyś wszedł, altcha wymaga
  `worker-src blob:` (web worker z blob URL).

### D. Testy

Istniejące testy wizardu (POST kroku 0 bez ALTCHA) **nie mogą się wywalić** →
w środowisku testowym `ZGLOS_CAPTCHA_ENABLED=False` domyślnie (żeby cała
dotychczasowa suita `zglos_publikacje` przechodziła bez zmian).

Nowe testy (`test_zglos_captcha.py`), z `@override_settings(
ZGLOS_CAPTCHA_ENABLED=True, ALTCHA_HMAC_KEY=<test>)` + mock weryfikacji
django-altcha. **Replay-testy MUSZĄ dodatkowo override'ować cache na locmem**
(`CACHES={"default": LocMemCache}`), bo test.py dziedziczy DummyCache →
`is_challenge_used()` inaczej zawsze `False` (test niczego nie dowodzi):
1. Anonim na kroku 0 → forma MA `AltchaField` (renderuje `<altcha-widget>`).
2. Zalogowany na kroku 0 → forma NIE ma pola (bramka anon-only).
3. Anonim, brak/nieprawidłowe rozwiązanie → krok 0 nieważny, brak awansu.
4. Anonim, poprawne rozwiązanie (mock verify OK) → awans na krok 1 +
   `session["zglos_captcha_ok"] == True`.
5. **Rewalidacja/late (przeformułowane):** po przejściu kroku 0 (flaga w sesji),
   pełne dojście do `render_done` → **`done()` dochodzi do skutku (zgłoszenie
   powstaje), a wizard NIE cofa na krok 0**. (Uwaga: bez flagi objaw to nie
   500, lecz `render_revalidation_failure` → 200 + powrót na krok 0; asercja
   „brak 500" byłaby zbyt słaba i przeszłaby nawet bez flagi — dlatego test na
   „done() się wykonał / brak cofnięcia".)
6. Replay: to samo rozwiązanie użyte dwa razy (z locmem cache) → drugie
   odrzucone jako „already used".
7. `ZGLOS_CAPTCHA_ENABLED=False` → forma bez pola nawet dla anonima
   (dowód, że dotychczasowa suita nie jest ruszona).
8. System-check WARNING: `@override_settings(ZGLOS_CAPTCHA_ENABLED=True,
   ALTCHA_HMAC_KEY=<sentinel/placeholder>)` → `run_checks`/wywołanie funkcji
   check zwraca `checks.Warning` (poziom Warning, NIE Error — build nietknięty).
   Odwrotnie: realny klucz + ON → brak warninga; OFF + placeholder → brak
   warninga. (Bez importu `production.py` w procesie testu — check operuje na
   aktywnych `settings`, więc żadnej mutacji współdzielonych dictów base.)

### E. Wdrożenie (osobny PR w bpp-deploy)

- **Auto-generacja klucza:** w `scripts/ensure-config-files.sh`, obok innych
  `_ensure_secret`:
  ```sh
  _ensure_secret ALTCHA_HMAC_KEY "$(openssl rand -hex 32)"   # 64-hex
  ```
  `_ensure_secret` jest **idempotentny** (dodaje do `.env` tylko gdy brak, nie
  nadpisuje) i odpala się na **każdym `make up`** → wszystkie instalacje
  (świeże i po upgrade) dostają stabilny klucz bez ręcznego kroku. To eliminuje
  breaking-upgrade przy default ON.
- **Wpięcie env** `ALTCHA_HMAC_KEY` do **appservera, workerserver i
  beatserver** w compose (guard/warning i sama weryfikacja odpalają się w
  każdym imporcie/procesie Django; wszystkie trzy jadą na production settings).
- Ten PR bpp-deploy jest niezależny od PR-a bpp (captcha działa dopiero z oboma;
  do czasu — `ZGLOS_CAPTCHA_ENABLED` można trzymać OFF).

## Świadome ograniczenia

- PoW nie blokuje pojedynczego zdeterminowanego bota z zapleczem obliczeniowym
  — podnosi **koszt** masowego wysyłania. To celowo dobrany trade-off
  (prywatność + self-host) vs managed challenge (Turnstile/hCaptcha).
- Tempo dalej ograniczalne dodatkowo rate-limitem na endpoint (osobny temat).
- **Flow edycji (`edycja_zgloszenia/<uuid:kod_do_edycji>`)** używa tego samego
  wizardu → anonimowy autor poprawiający zwrócone zgłoszenie z linku e-mail
  też dostanie PoW na kroku 0. **Świadomie akceptujemy** — to nadal anonimowy
  zapis, a edycje są rzadkie; jeden PoW na wejście w edycję jest do przyjęcia.
- **Sentinel/placeholder klucz = forgeable captcha (cicho).** Instalacja
  omijająca auto-gen bpp-deploy i nie ustawiająca klucza uruchomi captchę na
  sentinelu → HMAC znany → obejście PoW. **Identyczny profil ryzyka jak
  `SECRET_KEY`** (repo też nie fail-fastuje). Mitygacja: auto-gen pokrywa realne
  wdrożenia; system-check WARNING sygnalizuje placeholder. Świadomy trade-off
  prostoty (brak build-time trapów) vs twardego fail-fast.

## Poza zakresem

- Rate-limiting/throttling endpointu (osobno).
- CAPTCHA na innych formularzach (tylko zgłoszenia).
- Zmiana domyślnej publiczności formularza.
