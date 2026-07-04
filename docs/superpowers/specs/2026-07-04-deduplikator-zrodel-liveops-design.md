# Deduplikator źródeł — skanowanie w tle (Celery) z live-progress (django-liveops)

Data: 2026-07-04
Status: zatwierdzony do implementacji

## Problem

`src/deduplikator_zrodel` działa wolno. Przyczyna: widok
`duplicate_sources_view` na **każdym załadowaniu strony** woła
`znajdz_pierwszego_zrodlo_z_duplikatami()` — liniowy skan po 200+ źródłach,
gdzie dla każdego źródła uruchamiane jest kilka zapytań trigram-similarity
(`analiza_duplikatow` → `znajdz_podobne_zrodla` → `ocen_podobienstwo`).
Każde „skip"/„oznacz"/redirect ponawia cały skan. `cacheops` maskuje to
tylko przy ciepłym cache; przy zimnym (po każdej modyfikacji danych)
strona wisi.

Wzorzec docelowy istnieje już w `src/deduplikator_autorow`: skan w tle
(Celery) zapisuje trwałe wyniki, a UI czyta prekalkulowane pary. Autorzy
używają jednak **ręcznie napisanego** pollingu AJAX (`DuplicateScanRun` +
`scan_status_view`). Tu robimy to samo architektonicznie, ale postęp
prezentujemy przez **django-liveops** (WebSocket + HTMX, bez pollingu),
co jednocześnie upraszcza kod (model operacji + transport dostaje framework).

## Cel

1. Wyszukiwanie duplikatów źródeł jako **procedura w tle na Celery**.
2. **Live-progress** przeszukiwania bazy przez `django-liveops`.
3. Po zakończeniu — **lista wszystkich par duplikatów** (wzorem
   deduplikatora autorów), z akcjami per-wiersz.

## Kontekst — zgodność środowiska (zweryfikowane)

- Python `>=3.11` (liveops wymaga 3.11+) ✓
- Django 5.2.15 (liveops wymaga 5.2+) ✓
- `channels`, `daphne`, `channels_broadcast` w `INSTALLED_APPS` ✓
- `ASGI_APPLICATION = "django_bpp.asgi.application"`, `ProtocolTypeRouter`
  + `URLRouter` już skonfigurowane ✓
- `CHANNEL_LAYERS` (Redis) skonfigurowane ✓
- Celery działa (`django_bpp.tasks`) ✓
- `django-liveops` 0.3.0 dostępny na PyPI (`requires-python >=3.11`) ✓

## Jak działa django-liveops (skrót istotny dla designu)

- Deweloper pisze **jedną metodę** `run(self, p: Progress)` na konkretnej
  podklasie abstrakcyjnego modelu `liveops.models.LiveOperation`.
- `LiveOperation` **jest** rekordem operacji: UUID PK, `owner`,
  `created_on`/`started_on`/`finished_on`, `finished_successfully`,
  `cancel_requested`/`cancelled`, `traceback`, `result_context` (JSON),
  opcjonalne `stages`. Zastępuje ręczny `DuplicateScanRun`.
- `Progress` API: `p.track(iterable, total=, label=)` (iteruje, aktualizuje
  procent, sprawdza anulowanie), `p.log(line)`, `p.status(text, level)`,
  `p.percent(v)`, `p.result(context=...)`, `p.error(msg)`,
  `p.check_cancelled()`.
- `op.enqueue()` dispatchuje wg `LIVEOPS["RUNNER"]`.
  `RUNNER="celery"` → shared task Celery (produkcja). `RUNNER="eager"` →
  synchronicznie w wątku żądania (testy, bez Redis/workera).
- Widoki wbudowane: `CreateLiveOperationView`, `LiveOperationView`
  (strona live-host z paskiem postępu), `CancelView`, `RestartView`,
  `LiveOperationListView`. Bazowy mixin `BaseLiveOperationMixin`:
  login-required + opcjonalny `LIVEOPS["REQUIRED_GROUP"]`, queryset
  zawężony do `owner=request.user`.
- Tag szablonu `{% live_operation op %}` renderuje kontener z kanałem
  i tokenem; `liveops.js` subskrybuje WebSocket. Host-template nazwa
  auto-derived: `<app_label>/<snake(Class)>.html`; result-template
  `<app_label>/<snake(Class)>_result.html`.

## Architektura

### 1. Zależność i integracja (poziom projektu)

- `pyproject.toml`: dodać `django-liveops[celery]>=0.3,<0.4`. Przeliczyć
  `uv.lock` (`uv sync`).
- `settings/base.py`:
  - `INSTALLED_APPS`: dodać `"liveops"` (channels/channels_broadcast już są).
  - `LIVEOPS = {"BASE_TEMPLATE": "base.html", "RUNNER": "celery",
    "THROTTLE_HZ": 10}`.

#### JS — pojedyncza inicjalizacja socketu (KRYTYCZNE, wynik review)

BPP już ładuje globalnie **htmx** (`bundle-entry.js:22-23`,
`window.htmx`) oraz **channels_broadcast** `notifications.js`
(`bundle-entry.js:65`, `window.channelsBroadcast`), a `base.html:169`
woła `channelsBroadcast.init(<extra-channels>)` na `$(document).ready`.
`liveops.js` na `DOMContentLoaded` woła `cn.init(null,
{subscriptionToken})` — z `null` extra-channels, więc **zastępuje**
subskrypcję socketu (`liveops.js:213`; init jest re-entrant i zamyka
poprzedni socket). Dwie inicjalizacje na tej samej stronie „walczą" —
ostatnia wygrywa i zamyka socket poprzedniej. To realny, zależny od
kolejności bug.

Strategia (odejmowanie, nie dodawanie):

- **Host-template ładuje TYLKO `liveops/liveops.js`** — NIE htmx ani
  notifications.js (są już w globalnym bundlu). Ładowanie vendored htmx z
  liveops nadpisałoby `window.htmx`; ponowne wykonanie notifications.js
  nadpisałoby żywy `channelsBroadcast`.
- **`base.html`**: owinąć wywołanie `channelsBroadcast.init(...)` w
  nadpisywalny blok `{% block channels_broadcast_init %}...domyślne...
  {% endblock %}` (zmiana 1-liniowa, zero zmian zachowania dla innych
  stron). Host-template nadpisuje ten blok **pusty** → `liveops.js` jest
  jedynym inicjalizatorem socketu na stronie skanu. Globalne toasty
  powiadomień są na czas trwania strony skanu wyciszone (strona
  przejściowa — akceptowalne). `liveops.js` nadpisuje `addMessage`
  delegując nieznane typy do oryginału (`liveops.js:207`), więc
  powiadomienia BPP działają wszędzie indziej bez zmian.
- **Auto-redirect po sukcesie**: `ScanZrodelForDuplicates.get_success_url()`
  zwraca URL listy. `liveops.js` na `liveop_finished` z `FINISHED_OK`
  robi `window.location.assign(success_url)` (`liveops.js:189-190`) —
  automatyczne przejście skan→lista, bez ręcznego linku. Link w
  result-template zostaje jako fallback bez-JS.
- **Lista jest zwykłą stroną** (bez `liveops.js`) — pokazuje kandydatów
  ostatniego ukończonego skanu, nie wymaga live-update. Globalny init z
  `base.html` działa tam normalnie.
- `settings` testowe: `LIVEOPS["RUNNER"] = "eager"` (skan synchroniczny,
  bez Redis/workera). Ustawić w konfiguracji testów tak, aby nie wpływało
  na produkcję.
- `django_bpp/asgi.py`: **zastąpić** import
  `channels_broadcast.routing.websocket_urlpatterns` przez
  `liveops.routing.websocket_urlpatterns`. `LiveOperationConsumer`
  **dziedziczy po** `NotificationsConsumer` (nadzbiór: obsługuje realne
  powiadomienia przez `super()` **oraz** snapshoty `liveop.*`), a obie
  listy bindują ten sam path `asgi/notifications/` — więc to drop-in
  replacement, a nie konkatenacja. Powiadomienia channels_broadcast
  działają dalej bez zmian.
- `django_bpp/urls.py`: zamontować raz centralny router liveops:
  `path("live/", include("liveops.urls"))`. `op.get_absolute_url()`
  reversuje `liveops:live` (`<op_type>/<uuid:pk>/`) dla każdej podklasy —
  bez per-app wiringu WS/URL. Widoki create/list zostają app-specific
  (nasz `start_scan` + lista).

### 2. Modele (`deduplikator_zrodel/models.py`) — jedna migracja

- **`ScanZrodelForDuplicates(LiveOperation)`** — konkretna podklasa.
  Skan = ten rekord. Pola prezentacyjne (poza tym, co daje liveops):
  - `total_sources` (PositiveInteger)
  - `sources_scanned` (PositiveInteger)
  - `duplicates_found` (PositiveInteger)
  - metoda `run(self, p)` deleguje do `perform_scan(self, p)`
    (patrz sekcja 3).
- **`SourceDuplicateCandidate`** — trwała para (wzorem
  `deduplikator_autorow.DuplicateCandidate`, ale lżejsza — źródła nie są
  masowo kasowane, więc renderujemy przez `select_related`, nie przez
  gruby snapshot):
  - `scan` → FK do `ScanZrodelForDuplicates` (`related_name="candidates"`,
    `on_delete=CASCADE`)
  - `main_zrodlo` / `duplicate_zrodlo` → FK `bpp.Zrodlo`
    (`on_delete=CASCADE`, `related_name` rozłączne)
  - `confidence_score` (Integer, indeks)
  - **Bez grubego snapshotu.** Lista i XLSX renderują przez
    `select_related("main_zrodlo__pbn_uid", "duplicate_zrodlo__pbn_uid")`
    — `slug`, `nazwa`, `issn`, `e_issn`, `pbn_uid`, `mniswId` czytane na
    żywo (lista to jeden skan, ograniczona liczba par → 2-3 joiny są
    tanie, brak N+1). Powód porzucenia snapshotu: (a) `przemapuj` reversuje
    po `kandydat.slug` (którego w snapshotcie nie było — finding 5),
    (b) źródło skasowane po scaleniu i tak kasuje wiersz kandydata przez
    CASCADE, więc snapshot „na wypadek usunięcia" jest zbędny.
  - Jedyne cache'owane pola (fallback do wyświetlenia wiersza MERGED, gdy
    źródło zniknie tuż przed renderem): `main_nazwa`, `duplicate_nazwa`
    (CharField). `main_pub_count` / `duplicate_pub_count` (PositiveInteger)
    — użyte też przy kanonikalizacji, warto mieć zapisane.
  - `status`:
    - `PENDING` — „do sprawdzenia" (domyślne, pokazywane na liście)
    - `SKIPPED` — „odłożony na później"
    - `MERGED` — „przemapowany/scalony"
    - (`NOT_DUPLICATE` i `IGNORED` **nie** są statusem — wynikają
      dynamicznie z `NotADuplicate` / `IgnoredSource`; patrz filtr listy
      w §4, finding 6.)
  - `reviewed_at` (DateTime null), `reviewed_by` (FK User null,
    `on_delete=SET_NULL`)
  - `created_at` (auto_now_add)
  - `Meta`: `ordering = ["-confidence_score"]`; indeks `["scan",
    "status"]`; **unikalny constraint na NIEUPORZĄDKOWANĄ parę w obrębie
    skanu wyrażeniem** (finding 4): `UniqueConstraint(Least("main_zrodlo",
    "duplicate_zrodlo"), Greatest("main_zrodlo", "duplicate_zrodlo"),
    "scan", name="uniq_scan_unordered_pair")` (expression constraint, OK
    na Django 5.2). To twardy backstop niezależny od kanonikalizacji w
    kodzie (która zależy od `pub_count` mogącego się zmienić w trakcie).
- `IgnoredSource` / `NotADuplicate` — bez zmian.
- **Uwaga (finding 12)**: `owner` (z `LiveOperation`) jest FK
  `on_delete=CASCADE` i **nie można go nadpisać** w podklasie (Django
  zabrania redeklaracji pola z abstract base). Usunięcie użytkownika
  kasuje jego skany i — przez `scan` CASCADE — ich kandydatów. To tylko
  kolejka robocza (regenerowalna re-skanem); trwały stan przeglądu
  (`NotADuplicate`/`IgnoredSource`) przeżywa (ma `SET_NULL`). Do
  udokumentowania, bez zmiany.

### 3. Skan (`deduplikator_zrodel/operations.py`)

- `ScanZrodelForDuplicates.run(self, p)` deleguje do czystej, testowalnej
  funkcji `perform_scan(operation, p)`:
  1. Zbuduj bazowy queryset źródeł-kandydatów (jak dziś w
     `znajdz_pierwszego_zrodlo_z_duplikatami`: `pub_count > 0`,
     `pbn_uid__mniswId__isnull=False` — patrz zakres w §Ryzyka),
     policz `total`; zapisz `operation.total_sources`. Iteruj queryset
     przez `.iterator()` (finding 11 — nie ładuj wszystkich w pamięć).
  2. Wyczyść ewentualne stare `SourceDuplicateCandidate` tego skanu
     (idempotencja przy restarcie).
  3. `for zrodlo in p.track(sources_iterator, total=total,
     label="Skanowanie źródeł")`: użyj `utils.znajdz_podobne_zrodla(
     zrodlo)` + `utils.ocen_podobienstwo(zrodlo, kandydat)`; dla par ze
     `score > 0` zapisz `SourceDuplicateCandidate` **raz** na
     nieuporządkowaną parę.
     - **Kanonikalizacja pary**: main = źródło o większej liczbie
       publikacji (remis → mniejszy `pk`), duplicate = drugie. Zbiór
       `seen` par `(min_pk, max_pk)` w pamięci procesu skanu chroni przed
       lustrzanym duplikatem; expression-constraint w DB to twardy
       backstop. Zapisz `confidence_score` = score z chwili odkrycia
       (finding 10: `ocen_podobienstwo` jest kierunkowe, a przy odwróceniu
       pary przez kanonikalizację liczba dotyczy kierunku odkrywca→kandydat,
       nie main→duplicate; różnice są bliskie zeru w praktyce, ale wynik
       jest lekko zależny od kolejności — akceptowane, udokumentowane).
     - Pomijaj pary już w `NotADuplicate` / z `IgnoredSource` — te filtry
       są już wewnątrz `znajdz_podobne_zrodla`/`_candidates_queryset`,
       więc dziedziczymy je „za darmo".
     - **Batch progresu (finding 11)**: `operation.sources_scanned`
       zapisuj do DB co K źródeł (np. co 25) i na końcu, nie po każdym —
       inaczej N dodatkowych UPDATE-ów. `p.track` sam throttluje procent.
       Okresowo `p.log(...)`.
  4. Zapisz `operation.duplicates_found`, `p.result(context={
     "duplicates_found": n})`. Przejście do listy realizuje
     `get_success_url()` (auto-redirect, §1), nie kontekst wyniku.
- **Guard „jeden skan naraz" z progiem świeżości (finding 3)**: przy
  starcie odrzuć **tylko** jeśli istnieje nieukończony
  `ScanZrodelForDuplicates` (stan `NOT_STARTED`/`STARTED`) **młodszy niż
  próg** (np. `created_on` w ostatnich 2h). Starszy nieukończony skan =
  osierocony (martwy worker / zgubiony task Celery — `CancelView` ustawia
  tylko `cancel_requested`, a `cancelled` ustawia dopiero runner, więc
  bez workera skan wisi w `STARTED` na zawsze) → nie blokuje nowego.
  Dodatkowo admin action „oznacz jako nieudany/anuluj" na osierocone skany.
- `run()` nie łapie `except Exception: pass` — liveops sam ustawia
  `traceback`/`error` przy wyjątku; ewentualne własne `try` tylko wąskie
  i z logiem (zgodnie z regułą projektu).

### 4. Widoki i URL-e (`deduplikator_zrodel`)

Zachowujemy **nazwę** URL `duplicate_sources` (linkują do niej
`top_bar.html`, `crossref_bpp/duplikaty.py`, test
`crossref_bpp/tests/test_repro_fd422.py`) — repointing tej nazwy na nowy
widok listy jest bez-dotykowy dla callerów.

- **`duplicate_sources` (nazwa zachowana) → nowy widok listy**:
  - Pokazuje `SourceDuplicateCandidate` z **ostatniego ukończonego**
    skanu, `select_related("main_zrodlo__pbn_uid",
    "duplicate_zrodlo__pbn_uid")`, sort po `-confidence_score`.
  - **Dynamiczne wykluczenie (finding 6)**: z listy znikają kandydaci,
    których którakolwiek strona jest w `IgnoredSource`, lub których para
    jest w `NotADuplicate` (filtr na zapytaniu, nie mutacja kandydatów).
    Dzięki temu „ignoruj"/„nie duplikat" działają natychmiast na
    **wszystkie** wiersze zawierające dane źródło/parę, bez re-skanu i bez
    bookkeepingu statusu.
  - Filtr `status`: domyślnie `PENDING`; przełącznik „odłożone"
    (`SKIPPED`).
  - Nagłówek: data ostatniego skanu + liczba znalezionych + przycisk
    **„Skanuj bazę"** (POST → `start_scan`). Gdy trwa skan **bieżącego
    użytkownika** — link do jego strony live; gdy trwa skan **innego**
    admina (finding 8: strony live są `owner`-scoped, obcy dostałby 404) —
    pasywny komunikat „Skanowanie w toku (uruchomił: X)", bez linku.
  - Akcje per-wiersz: **przemapuj** (istniejący URL
    `przemapuj_zrodlo:przemapuj` + `?zrodlo_docelowe=<main_pk>`, slug z
    `select_related`), **oznacz „nie duplikat"** (`mark_non_duplicate`),
    **ignoruj** (`ignore_source`), **odłóż** (`skip_candidate`), a w
    widoku odłożonych **cofnij** (`unskip_candidate`).
  - Gdy brak jakiegokolwiek ukończonego skanu — komunikat „Uruchom
    pierwsze skanowanie".
- **`start_scan` (POST, gate `GR_WPROWADZANIE_DANYCH`)**: tworzy
  `ScanZrodelForDuplicates(owner=request.user)`, `enqueue()`, redirect na
  `op.get_absolute_url()` (strona live liveops). Guard „jeden skan naraz".
- **`skip_candidate` (POST)**: `PENDING → SKIPPED` dla wskazanego
  kandydata; redirect do listy.
- **`unskip_candidate` (POST)**: `SKIPPED → PENDING`; redirect do listy.
- **`reset_skipped` (POST, nazwa zachowana)**: masowo `SKIPPED → PENDING`
  dla ostatniego skanu (dawniej: czyszczenie sesji).
- **`mark_non_duplicate` / `ignore_source`** — zachowane: tworzą wpis w
  `NotADuplicate` / `IgnoredSource` i redirect do listy. **Nie** mutują
  kandydatów — wykluczenie realizuje dynamiczny filtr listy (finding 6),
  więc jedna akcja zdejmuje z listy wszystkie dotknięte wiersze.
- **`download_duplicates_xlsx`** — zachowany; źródłem danych stają się
  `SourceDuplicateCandidate` ostatniego skanu (`select_related`, z tym
  samym dynamicznym wykluczeniem co lista), zamiast liczenia w locie.
- **Usuwane**: `skip_current`, `go_previous` oraz cała logika sesyjna
  `skipped_sources` (zastąpione trwałym `status` kandydata). Widok
  „jedno źródło po drugim" znika — landing to lista.
- Host-template `deduplikator_zrodel/scan_zrodel_for_duplicates.html`
  (extends `base.html`, `{% block channels_broadcast_init %}{% endblock %}`
  **pusty** by wyłączyć podwójny init socketu, ładuje **tylko**
  `liveops/liveops.js`, renderuje `{% live_operation op %}`; szczegóły w
  §1 „JS — pojedyncza inicjalizacja"). `ScanZrodelForDuplicates`
  implementuje `get_success_url()` → URL listy (auto-redirect po
  sukcesie). Result-template `deduplikator_zrodel/
  scan_zrodel_for_duplicates_result.html`: „Znaleziono N duplikatów"
  + link do listy (fallback bez-JS).

### 5. Admin

- Rejestracja `ScanZrodelForDuplicates` (read-mostly: lista skanów,
  status, liczniki, data) i `SourceDuplicateCandidate` (podgląd par,
  filtr po statusie/scanie) — wzorem adminów w `deduplikator_autorow`.
  Emoji zamiast Foundation Icons (reguła projektu dla `templates/admin`).

## Testy

pytest + `model_bakery.baker`, testcontainers (PostgreSQL trigram).
`LIVEOPS["RUNNER"] = "eager"` w konfiguracji testowej.

- `perform_scan` zapisuje kandydatów dla realnych par (fixture: dwa
  źródła z tym samym `pbn_uid`/ISSN i publikacjami).
- Kanonikalizacja: lustrzana para zapisana **raz**; main = źródło o
  większej liczbie publikacji.
- Tylko `score > 0` trafia na listę.
- Wykluczenia: para w `NotADuplicate` oraz źródło w `IgnoredSource` nie
  pojawiają się w wynikach.
- `total_sources`/`sources_scanned`/`duplicates_found` ustawione poprawnie.
- Widok listy renderuje kandydatów ostatniego skanu; filtr
  PENDING/SKIPPED działa.
- `start_scan`: gate `GR_WPROWADZANIE_DANYCH` (403/redirect dla obcego),
  guard „jeden skan naraz" (drugi start odrzucony), tworzy operację i
  redirectuje na stronę live.
- `skip_candidate`/`unskip_candidate`/`reset_skipped` zmieniają status
  zgodnie z oczekiwaniem.
- `mark_non_duplicate`/`ignore_source` tworzą wpisy w
  `NotADuplicate`/`IgnoredSource` i zdejmują kandydata z listy.
- XLSX export zwraca plik na bazie kandydatów ostatniego skanu.

## Migracja / baseline

- Jedna migracja: `ScanZrodelForDuplicates` + `SourceDuplicateCandidate`.
  (`LiveOperation` jako abstract base — jego pola wejdą do tabeli
  podklasy.) **Nie modyfikować istniejących migracji.**
- Po dodaniu migracji: `make baseline-update` (delta), commit
  `baseline-sql/baseline.sql` + `baseline.meta.json`. Baseline odświeżamy
  raz, przy scalaniu (nie w równoległych branchach).

## Poza zakresem (YAGNI)

- Stepper etapów (skan jest jednofazowy).
- Przeglądanie historii wielu skanów w UI (admin wystarcza).
- Auto-scalanie / automatyczny merge.
- Skanowanie cykliczne (cron/beat).

## Ryzyka / uwagi

- **JS — podwójny init socketu (BLOCKER, rozwiązane)**: pełna strategia
  w §1 „JS — pojedyncza inicjalizacja". Skrót: host-template ładuje tylko
  `liveops.js`, wygasza init z `base.html` przez pusty blok, auto-redirect
  po sukcesie przez `get_success_url()`.
- **Zakres skanu / kompletność (finding 7)**: bazowy queryset wymaga
  `pbn_uid__mniswId__isnull=False` — pary, w których **żadna** strona nie
  ma ministerialnego ID, nie są enumerowane. To **zamierzony zakres** i
  **nie regresja**: obecne `znajdz_pierwszego_zrodlo_z_duplikatami`
  używa identycznego `base_queryset` (mnisw-restricted) we wszystkich
  trzech próbach seeda. Nowy skan jest ściśle lepszy — usuwa dzisiejszy
  limit „pierwsze 100 ISSN + 100 po nazwie". W UI listy dopisek „skan
  obejmuje źródła z ministerialnym ID". Poszerzenie zakresu = przyszłość
  (YAGNI).
- **`REQUIRED_GROUP` vs superuser**: nie polegamy na
  `LIVEOPS["REQUIRED_GROUP"]` — bramkujemy własnym
  `group_required(GR_WPROWADZANIE_DANYCH)` (przepuszcza superusera) na
  `start_scan`/liście. Strony live liveops są i tak `owner`-scoped
  (konsekwencja dla obcych adminów: §4, finding 8).
- **Guard race (finding 9)**: check-then-create dopuszcza teoretycznie
  dwa równoległe skany między dwoma POST-ami. Akceptowalne dla narzędzia
  tylko-admin; próg świeżości (§3) i tak ogranicza szkodę. Bez
  partial-unique-index (nadmiarowa złożoność).
- **Anulowanie**: `p.track()` woła `check_cancelled()` — „Anuluj" z UI
  liveops działa bez dodatkowego kodu.
- **Idempotencja restartu**: `perform_scan` czyści stare kandydatury
  swojego skanu na wejściu (`RestartView` też woła hook czyszczący).
