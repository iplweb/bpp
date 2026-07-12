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
  - **`local.py` (dev/run-site):** efemeryczny klucz **tylko gdy env nieustawiony**
    — `os.environ.setdefault("ALTCHA_HMAC_KEY", secrets.token_hex(32))` PRZED
    importem `base` (dokładnie wzorzec `DJANGO_BPP_SECRET_KEY` w `local.py`).
    Dzięki temu precedencja jest jednoznaczna (fix codex): `run-site` bez env →
    losowy klucz (widget działa, nic forgeable w repo); dev `docker compose up`
    ładuje `.env.docker` → `setdefault` NIE nadpisuje placeholdera.
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
  Widoczność (doprecyzowanie po codex): `collectstatic` uruchamia **tylko**
  checki z tagiem `staticfiles`, więc nasz zwykły check **nie odpali się na
  buildzie** — to dobrze, build pozostaje wykonywalny niezależnie od poziomu
  (Warning i tak nie wywala). Ostrzeżenie pojawia się przy `manage.py check`
  i `migrate` (entrypoint robi `migrate`), NIE „na dowolnym starcie komend"
  ani pod czystym gunicorn/daphne. **Realną gwarancję klucza w prod daje
  auto-gen bpp-deploy, nie ten check** — check to best-effort sygnał dla
  operatora, nie mechanizm bezpieczeństwa.
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

- **Marker trzymamy w `self.storage.extra_data`, NIE w `request.session`**
  (KRYTYCZNE po review codex). Sesja ma zasięg wielu przebiegów wizardu:
  GET na URL wizardu resetuje TYLKO storage wizardu (`views.py` `get()`),
  nie sesję — więc flaga sesyjna po jednym PoW odblokowałaby wiele zgłoszeń
  pętlą „rozwiąż PoW → GET-restart → nowe zgłoszenie bez PoW". `extra_data`
  resetuje się RAZEM z wizardem (jak `pliki_list`), więc restart wymusza nowy
  PoW. Klucz: `PLIKI…`-analogiczny `ZGLOS_CAPTCHA_OK_KEY = "captcha_ok"`.
- `Zgloszenie_PublikacjiWizard.get_form_kwargs("0")` przekazuje
  `captcha_wymagany: bool` = `settings.ZGLOS_CAPTCHA_ENABLED` (czytane
  **call-time**) AND `not request.user.is_authenticated` AND
  NOT `self.storage.extra_data.get(ZGLOS_CAPTCHA_OK_KEY)`.
- `RodzajPublikacjiForm.__init__(captcha_wymagany=False)`: dodaje `AltchaField`
  **tylko** gdy `captcha_wymagany`. Inaczej pole nieobecne. (Forma dostaje sam
  bool — nie potrzebuje całego `request`.)
- Po ważnym POST kroku 0 z zweryfikowanym ALTCHA (`AltchaField.validate`) →
  wizard ustawia `extra_data[ZGLOS_CAPTCHA_OK_KEY] = True` w
  **`process_step` dla kroku "0"** (istniejący override obsługuje dziś tylko
  "2" — dodać branch "0"). `process_step` wykonuje się PRZED `set_step_data`
  i przed czyszczeniem cache warunków, więc marker jest na miejscu, zanim
  cokolwiek rewaliduje krok 0.
- Rewalidacja w `render_done`: marker ustawiony → `captcha_wymagany=False` →
  pole nieobecne → brak ponownej weryfikacji, `done()` dochodzi do skutku.
- Nie trzeba osobno czyścić markera w `done()` — `render_done` po udanym
  `done()` i tak robi `storage.reset()` (zeruje `extra_data`). GET-restart
  również. Czyli: 1 PoW = 1 przebieg wizardu (a przebieg → co najwyżej 1
  zgłoszenie w `done()`).

**Znane, zaakceptowane ograniczenie:** w RAMACH jednego przebiegu PoW nie broni
wielokrotnego uploadu tmp (pętla krok 0→2→2…) — ale to i tak nie tworzy
rekordów (dopiero `done()`), a upload-DoS to temat **rate-limitu**, nie CAPTCHY
(sprzątanie tmp pokrywa naprawa #2 + cron co 6h).

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
- **`auto="onload"`** (NIE `onsubmit` — ustalenie po review codex): kafelki
  kroku 0 wołają `form.submit()` **bezpośrednio** (`step_rodzaj.html`), co
  **omija zdarzenie `submit`**, na którym widget przechwyciłby formularz przy
  `onsubmit` → PoW nigdy by się nie policzył. `onload` liczy PoW przy
  załadowaniu strony (gotowy zanim user kliknie kafelek). To też pokrywa
  re-solve po spaleniu challenge (`mark_challenge_used` odpala się w `validate`
  niezależnie od reszty pól). Alternatywa `form.requestSubmit()` w JS +
  `onsubmit` — odrzucona (więcej zmian + wymaga browser-testu).
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
   `storage.extra_data[ZGLOS_CAPTCHA_OK_KEY] == True`.
4b. **GET-restart (regresja HIGH 1):** rozwiąż krok 0 (marker w extra_data) →
   GET na URL wizardu (storage.reset) → krok 0 znów MA `AltchaField` (marker
   wyzerowany razem z wizardem). Dowodzi, że jeden PoW NIE odblokowuje kolejnego
   przebiegu w tej samej sesji.
5. **Rewalidacja/late — NIE-tautologicznie (fix codex):** mock `verify_solution`
   podpięty tak, by **liczyć wywołania**. Pełny przebieg do `done()` →
   **weryfikator wołany DOKŁADNIE RAZ** (tylko POST kroku 0; przy rewalidacji
   w `render_done` pole nieobecne dzięki markerowi → brak drugiego wywołania),
   `done()` dochodzi do skutku. (Sama asercja „done() się wykonał" byłaby
   tautologiczna — z DummyCache i mockiem-zawsze-OK przeszłaby też bez markera;
   dlatego liczymy wywołania weryfikatora.)
6. Replay — na **poziomie pola/cache**, nie wizardu (fix codex): w tej samej
   sesji po pierwszym PoW pole znika (marker), więc replay trzeba testować
   **dwiema niezależnymi instancjami `AltchaField`/klientami** dzielącymi
   **LocMemCache** (`@override_settings(CACHES=locmem)` — inaczej DummyCache =
   no-op): to samo rozwiązanie → drugie odrzucone jako „already used".
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
- **Twarda kolejność (fix codex — NIE „niezależne PR-y"):** przy default ON
  kod BPP nie może trafić na prod PRZED auto-genem, bo publiczny formularz
  ruszyłby na sentinelu → captcha forgeable (tylko warning). W normalnym flow
  bpp-deploy jest to zapewnione: `make up` uruchamia `ensure-config-files`
  (generuje klucz do `.env`) **PRZED** `docker compose up` z nowym obrazem —
  więc klucz istnieje, zanim kontener z default-ON wstanie. Warunek: zmiana
  bpp-deploy (auto-gen + wpięcie env) musi być **wdrożona razem z / przed**
  obrazem BPP (standardowo: `git pull` bpp-deploy → `make up`). Nie deployować
  nowego obrazu BPP pod starym bpp-deploy.
- **Alternatywa zerowego ryzyka (do decyzji właściciela):** default **OFF** w
  BPP, a `ZGLOS_CAPTCHA_ENABLED=1` włączane osobno po potwierdzeniu dystrybucji
  klucza. Eliminuje zależność kolejności kosztem ręcznego włączenia.

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
