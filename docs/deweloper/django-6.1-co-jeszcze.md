# Django 6.1 — co jeszcze warto wziąć

Dokument roboczy powstały przy migracji BPP z Django 5.2 LTS na 6.1
(sierpień 2026). Zbiera to, czego migracja **nie** objęła, a co warto
rozważyć — razem z dowodami z kodu, szacunkiem kosztu i warunkami wyjścia.

Nie jest to lista życzeń przepisana z release notes. Każda pozycja była
sprawdzona w tym repozytorium; tam, gdzie sprawdzenie wykluczyło temat,
jest to zapisane, żeby nie wracał w dyskusji.

## Stan na wejściu

| Zrobione | Gdzie |
|---|---|
| Migracja na Django 6.1, Python >= 3.12 | PR #731 |
| `FETCH_PEERS` w adminie (N+1 → 2 zapytania) | PR #733 |
| `delete_confirmation_max_display` | w trakcie |
| Gate regresyjny na N+1 przez `FETCH_RAISE` | w trakcie |

## Sprawdzone i wykluczone — zero pracy

Odhaczone, żeby nie wracały:

- **Zmiana derywacji soli podpisanych ciasteczek.** Dotyczy wyłącznie
  `set_signed_cookie`/`get_signed_cookie`, których w kodzie nie ma.
  `cerif_export/oai/tokeny.py` używa gołego `signing.dumps`/`loads`
  z własną solą — mechanizm nietknięty (`django/core/signing.py`,
  `_cookie_signer_salt` / `_unsign_cookie`). Brak ryzyka na wdrożeniu,
  brak potrzeby ustawiania `SIGNED_COOKIE_LEGACY_SALT_FALLBACK`.
- **PBKDF2 1 200 000 → 1 500 000 iteracji.** `PASSWORD_HASHERS` nie jest
  nadpisane, więc wzmocnienie dziedziczy się za darmo. Hasła rehashują się
  przy kolejnym logowaniu.
- **Deprecacja `ModelAdmin.list_select_related = True`.** Nie dotyczy —
  25 wystąpień, wszystkie są listami albo dictami (dialekt
  `django-dynamic-admin-columns`), żadne nie jest `True`.
- **`GeneratedField` jako kolumny wirtualne.** Wymaga PostgreSQL 18,
  produkcja stoi na 16.
- **`StringAgg(distinct=True)` na SQLite, nowości Oracle.**
  Bezprzedmiotowe — baza to PostgreSQL.
- **Framework `Tasks` z Django.** BPP ma Celery + `django-liveops`
  + `celery-singleton`; migracja nie ma uzasadnienia.

## Kandydatury otwarte

### 1. `MAILERS` — nie opcja, tylko termin

**Dlaczego:** `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`
i cała rodzina są **deprecated w 6.1 i znikają w Django 7.0**. Dodatkowo
`fail_silently` przepada **bez zamiennika** — Django nie oferuje niczego
w zamian dla obsługi wyjątków.

**Stan w kodzie:**

- `settings/base.py` — `EMAIL_URL` przez `django-environ`
  (`env.email(...)` + `vars().update(EMAIL_CONFIG)`),
- `settings/production.py:177-183` — warunkowa podmiana `EMAIL_BACKEND`
  na `djcelery_email.backends.CeleryEmailBackend` plus doklejenie
  `djcelery_email` do `INSTALLED_APPS` w runtime,
- 4 użycia `fail_silently=True`: `pbn_api/client/publication_sync.py`
  (496, 574, 624) i `bpp/models/abstract/pbn.py:64`.

**Zysk poza samą zgodnością:** `MAILERS` ten kod **upraszcza**. Zamiast
warunkowej podmiany backendu w runtime wystarczy drugi alias
(`"async": {...}`) i jawne `send_mail(..., using="async")` tam, gdzie
faktycznie chcemy kolejkować. Znika magia w `production.py`.

**Uwaga:** przepisanie `fail_silently=True` na jawny `try/except` jest
zgodne z regułą projektu zakazującą cichego łykania wyjątków — więc to
nie tylko koszt, ale i porządek.

### 2. CSP — teraz w rdzeniu Django, więc znacznie taniej

**Dlaczego:** BPP nie ma dziś **żadnego** Content-Security-Policy. Django
6.1 daje to w rdzeniu, bez dodatkowej paczki:
`django.middleware.csp.ContentSecurityPolicyMiddleware`, ustawienia
`SECURE_CSP` / `SECURE_CSP_REPORT_ONLY`, tag szablonowy `csp_nonce_attr`,
check systemowy `security.W027` pilnujący spójności konfiguracji.
Szablony admina i wbudowane **same niosą już nonce**.

**Koszt — nie ukrywajmy go:** ok. **68 szablonów zawiera inline
`<script>`**. Każdy potrzebuje nonce albo wyniesienia do pliku.

**Zalecana ścieżka:** zacząć od `SECURE_CSP_REPORT_ONLY` na produkcji,
zebrać realne naruszenia z ruchu, dopiero potem zaostrzać. Pisanie polityki
na ślepo przy tej liczbie inline'ów skończy się rozbitym frontem.

Dobrze łączy się z pracami nad WCAG 2.2 AA.

### 3. `DB_CASCADE` punktowo na tabelach PBN

**Dlaczego:** kasowanie sesji importu PBN to dziś kaskada w Pythonie po
dziesiątkach tysięcy wierszy. `DB_CASCADE` (nowość 6.1) przenosi ją do
bazy — różnica rzędu wielkości.

**Dlaczego akurat tam, a nie wszędzie:** `DB_CASCADE` **nie odpala**
`pre_delete`/`post_delete`, więc jest groźne wszędzie, gdzie ktoś wisi na
sygnałach. Zweryfikowane dla `pbn_import` / `pbn_api` (19 wystąpień
`CASCADE`):

- **nie ma** ich w `DJANGO_EASY_AUDIT_REGISTERED_CLASSES` — to jawna
  allowlista, wyłącznie `bpp.*` i `zglos_publikacje.*`,
- brak `reversion.register`,
- brak `@denormalized` (django-denorm),
- nie obejmuje ich `django-soft-delete`.

**Nadal NIE tykać `bpp.*`** — tam denorm i reversion są istotne.

**Koszt:** wymaga migracji zmieniających `on_delete`, a więc również
odświeżenia baseline'u (`make baseline-update`).

### 4. `QuerySet.totally_ordered` — korektność, nie wydajność

**Dlaczego:** 73 miejsca z paginacją. Sortowanie niedeterministyczne
(pole z duplikatami, bez tie-breakera na `pk`) powoduje, że ten sam rekord
pojawia się na dwóch stronach, a inny znika. Klasa błędu niewidoczna aż do
zgłoszenia od bibliotekarza.

**Propozycja:** test asertujący `totally_ordered` na głównych listach
publicznych. Tanie, jednorazowe, łapie realną klasę błędów.

### 5. Dostępność formularzy admina — prawdopodobnie za darmo, ale trzeba obejrzeć

Django 6.1 przebudowało kolejność renderowania pól formularza admina
(etykieta → tekst pomocy → błędy → input) jako poprawkę dostępności.

Z szablonów formularzowych BPP nadpisuje **tylko `change_form.html`**, a
nie `includes/fieldset.html`, gdzie ta zmiana siedzi — więc poprawka
powinna się odziedziczyć bez pracy. **Ale testy tego nie łapią**: sprawdzają
zachowanie, nie układ. Trzeba zobaczyć okiem.

Wchodzi w ten sam przegląd admina, który i tak jest zalecany przed
produkcją — 6.1 usunęło klasę CSS `wide` i wyniosło `object-tools` poza blok
`content`, a w repo jest 64 nadpisanych szablonów admina.

### 6. Drobne, do rozważenia przy okazji

- **`RedirectView.preserve_request`** (307/308) — zachowuje metodę i ciało
  przy przekierowaniu. Kandydat w `zglos_publikacje`, gdzie są flow POST-owe.
  Wymaga potwierdzenia na konkretnym widoku.
- **`Permission.user_perm_str`** — drobna wygoda przy rozbudowanej
  maszynerii uprawnień (`django-tabular-permissions`, grupy).
- **`m2m_changed` z `raw=True` przy `loaddata`** — pozwala handlerom pominąć
  pracę przy ładowaniu fixtur. Istotne, bo django-denorm słucha sygnałów.
- **`QuerySet.in_bulk()` po `values()`/`values_list()`** — kosmetyka.

## Dług techniczny z warunkiem wyjścia

| Co | Warunek zdjęcia |
|---|---|
| `djangorestframework` pinowane z gita (`80d535dd`) | **Decyzja: zostaje**, nie czekamy na 3.18.0. Konsekwencja: DRF wypada z `pip-audit` (URL requirements) i buduje się ze źródeł. Pin wskazuje na SHA na `main`, więc jest trwały. Wymiana na `>=3.18` to jedna linijka, gdy wydanie się pojawi. |
| Shim `django.utils.itercompat` w `django_bpp/compat.py` | `django-admin-tools` 0.9.3 (ostatnie wydanie: sierpień 2023) ma martwy import usuniętego modułu. Do zdjęcia razem z odejściem od tej paczki albo po forku `django-admin-tools-iplweb` z usuniętą jedną linią. |
| `django-prometheus` usunięty z zależności | Stabilne 2.5.0 capuje `Django<6.1`; wsparcie jest dopiero w `2.6.0.devN`. Wrócić, gdy 2.6.0 wyjdzie stabilnie — jeśli integracja nadal ma być potrzebna. |

## Deprecacje 6.1 trafiające w kod (termin: Django 7.0)

Świadomie **nie** weszły do PR-a migracyjnego, żeby miał jeden czytelny
sygnał. To warningi, nie błędy — `filterwarnings = default`, więc nic nie
blokują. Osobny PR:

| Deprecacja | Miejsca |
|---|---|
| `BLANK_CHOICE_DASH` → `BLANK_CHOICE_LABEL` | `bpp/admin/core.py` (11, 430, 451), `pbn_api/admin/mixins.py` (2, 19) |
| `get_actions()` / `get_action_choices()` bez `action_location` | `bpp/admin/autor.py:559`, `bpp/admin/core.py` (430, 451), `bpp/admin/xlsx_export/mixins.py:286`, `rozbieznosci_dyscyplin/admin.py:334`, `pbn_api/admin/mixins.py:19` |
| Gołe `select_related()` bez argumentów | `import_dyscyplin/models.py` (381, 444), `ewaluacja_optymalizacja/utils.py` (324, 327), `pbn_api/adapters/wydawnictwo.py:397`, `bpp/models/zrodlo.py:243`, `bpp/models/szablondlaopisubibliograficznego.py:103` |
| `transaction.savepoint()` → `savepoint_create()` | `ewaluacja_optymalizacja/core/__init__.py:305`, `tasks/unpinning/simulation.py:48`, `tasks/unpinning/capacity_analysis.py:306`, `tasks/discipline_swap/simulation.py:36` |
| `EMAIL_*` → `MAILERS` | patrz pozycja 1 wyżej |

Zamiennikiem dla gołego `select_related()` jest — wg samego Django —
`FETCH_PEERS`, czyli mechanizm już włączony w adminie przez PR #733.

## Znany flake, niezwiązany z migracją

`komparator_pbn_udzialy::test_problem_wrapper_for_rozbieznosc` potrafi paść
na `IntegrityError` (`bpp_dyscyplina_naukowa_kod_key`). Przyczyna:
`baker.make("bpp.Dyscyplina_Naukowa", ...)` **bez jawnego `kod`** przy
unikalnym polu — model_bakery losuje wartość i dwa wywołania w jednym
teście potrafią się zderzyć.

Miejsca: `komparator_pbn_udzialy/tests/test_models.py` (158, 159, 193),
`tests/test_views.py` (47, 48). Naprawa: podać jawne `kod`.
