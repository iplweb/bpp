# Notatka na przyszłość: śledzenie operacji w tle + powiadomienia na żywo

> **STATUS: NOTATKA-NA-KIEDYŚ, NIE SPEC DO IMPLEMENTACJI.**
> Powstała z brainstormu 2026-06-02. Nic nie wdraża. Ma być punktem
> startu, gdy kiedyś wrócimy do tematu — żeby nie odtwarzać całej
> rozmowy. Temat jest realnie trudny (stan rozjeżdża się po DB ↔ Redis
> ↔ websockety, dochodzi reconcyliacja po stratnym kanale i eskalacja
> powiadomień). Świadomie odłożony.

Data: 2026-06-02. Gałąź: `feature/multi-hosted-config`.
Poprzednik koncepcyjny: `src/long_running/`.

## Problem (skąd to się wzięło)

`long_running` jest dobry w tym, co robi (śledzi start/koniec/status/
traceback operacji — `Operation` w `models.py`, ~170 stabilnych linii),
ale **trudny w użyciu**, i ból ma jedno źródło: progress jest *pushowany*
przez websockety. Z pushu wynikają dwa wyścigi (strona-jeszcze-nieotwarta
→ `LongRunningRouterView` z „poczekaj i przekieruj" + persystentny
`Notification` z ACK; oraz task-startuje-nim-wiersz-się-zacommituje →
pętla retry w `tasks.py`), plus boilerplate per-konsument (5 URL-i, 3
szablony, migracja). 12 konsumentów `long_running` w repo.

Śledzenie start/koniec **nie jest** problemem (i nie warto go zastępować
`django-celery-results` ani Django 6 `django.tasks` — to ruch w bok,
traci owner/formularz/wyniki). Problem to **dostarczanie progressu** i
**ergonomia**.

## Wizja: rozbicie na 2 nowe pakiety (+ istniejący `messages-extends`)

To są **dwa różne problemy**, które tylko spotykają się na końcu, a nie
jeden. **Śledzenie stanu zadań** (co leci, na ilu %, co padło) to inny
problem niż **dostarczanie komunikatu do usera na żywo na wszystkich
kartach**. Pierwsze nie potrzebuje websocketów (można odpytać API).
Drugie nie ma nic wspólnego z zadaniami — to generyczny kanał „powiedz
temu userowi coś, teraz, wszędzie gdzie patrzy" (równie dobrze: ogłoszenie
admina, „sesja zaraz wygaśnie"). Sklejanie ich w jeden pakiet zlepiałoby
dwie reusable rzeczy w jedną nie-reusable. Stąd **3 pakiety w stacku, ale
tylko 2 nowe**:

| # | Pakiet | Odpowiedzialność | Zależności | Ziarno w repo |
|---|--------|------------------|-----------|----------------|
| 1 | **`messages-extends`** *(już masz)* | trwały komunikat: model `Message` (user, body, `read`, level), render na stronie, auto-read-po-wejściu-na-URL | DB | — (3rd party, działa) |
| 2 | **`django-background-operations`** *(NOWY)* | `Operation` (UID/owner/status/traceback), `set/get_progress` (Redis), **API statusu** „oto Twoje zadania — 1 skończone, 5 trwa na X%, 3 z błędami", szuflada-widget | Redis + DB | `long_running.Operation` |
| 3 | **`django-live-messages`** *(NOWY, nazwa robocza)* | transport **na żywo** dla messages-extends: push nowego komunikatu na wszystkie karty usera + **sync zamknięcia** (zamknął na jednej → znika na pozostałych) | channels + messages-extends | `channels_broadcast` |

Oba nowe pakiety mają **ziarno w repo**, nie startują od zera:
- Pakiet 2 wyrasta z `long_running.Operation` (śledzenie start/koniec już
  działa).
- Pakiet 3 to **dorosła wersja `channels_broadcast`** — on już pushuje
  toasty websocketem (toastify) i ma pojęcie ACK. Brakuje mu (a) integracji
  z `messages-extends` (live-komunikat wygląda identycznie i jest trwały),
  (b) sync zamknięcia między kartami.

Obie apki **bpp-free od dnia zero** (`owner = settings.AUTH_USER_MODEL`) —
kandydaci do ekstrakcji jak `pbn_client`. Nie przebudowa `long_running`
w miejscu (przy 12 konsumentach zbyt ryzykowne): konsumenci migrują
pojedynczo, `long_running` znika gdy pusty.

### Pakiet 2: `django-background-operations`

- `Operation` (durable): UID (UUID), owner, start/koniec, status,
  traceback, `label`/`title` (ludzka nazwa do toastu/szuflady).
- `set_progress` / `get_progress` przez **Redis** (transient, poza
  transakcją — zapis natychmiast widoczny dla czytelników).
- **API statusu** + szuflada-widget: „oto Twoje zadania w tle".
- **Nie wie o powiadomieniach.** Tylko śledzi stan i wystawia go.
  Emituje sygnał `operation_finished` na zakończeniu.
- `test_app` w środku: (a) przykładowy `Operation`-subclass + trywialny
  task „licz do 100" pod testy integracyjne, (b) uruchamialna strona
  demo z paskiem.

### Pakiet 3: `django-live-messages` (nazwa robocza)

- Wysyła komunikat **wyglądający identycznie jak `messages-extends`** na
  wszystkie końcówki, na których siedzi user, **na żywo**.
- **Sync zamknięcia**: zamknięcie na jednej karcie → znika na pozostałych
  (zapis `read` w DB + broadcast eventu do grupy `user-{id}`).
- **Generyczny** — nie wie o operacjach. Użyteczny do dowolnego live-
  powiadomienia, nie tylko „zadanie skończone".
- Stoi na `messages-extends` (trwałość + render) + `channels` (transport).
- Alternatywne nazwy do rozważenia: `django-messages-live`,
  `django-realtime-messages`.

### Szew między pakietami — odwrócona zależność (klucz do rozłączności)

Pakiet 2 **nie zależy** od Pakietu 3. Operacja emituje tylko sygnał;
cienki **klej w projekcie** (BPP-owy, nie-pakiet) tłumaczy go na komunikat:

```
Operation kończy się  ──signal operation_finished──▶  glue (w projekcie)
                                       └─▶ live_messages.send(
                                             user, "Import skończył się po 3h…",
                                             persistent=decision_required)
```

Dzięki temu: Pakietu 2 użyjesz bez 3 (sam pasek, odpytywany przez API —
bez websocketów); Pakietu 3 użyjesz bez 2 (ogłoszenie admina — cokolwiek
live). Klej `*_bpp` zostaje w projekcie.

**Dlaczego 2 nowe, a nie 1 i nie 4:** nie 1 — monolit wiązałby Redis-
progress z websocketami z messages-extends, nie da się użyć kawałka osobno.
Nie 4 — frontend (szuflada, toast) zostaje w swoim pakiecie (każdy wozi
własny cienki JS/szablony); osobny pakiet „tylko frontend" to piekło
wersjonowania. YAGNI.

**To ta sama zasada, co dla `pbn_api`/`long_running`:** rozbicie na osobne
**apki Django w projekcie** z czystymi szwami jest **tanie** (greenfield,
zero podatku migracyjnego) i to dobra higiena, która *umożliwia* późniejszą
ekstrakcję bez jej *wymuszania*. Fizyczny `pip install` czeka aż pojawi się
**drugi konsument** spoza BPP.

## NAJWAŻNIEJSZE: taksonomia pojęć (to się zlewało)

Cztery **różne** byty. Mieszanie ich było źródłem zamętu:

Ta taksonomia mapuje się wprost na pakiety (patrz wyżej): byty #1/#2 →
Pakiet 2 (`django-background-operations`), byt #3 → Pakiet 3
(`django-live-messages`), byt #4 → istniejący `messages-extends`.

| # | Byt | Czas życia | Gdzie żyje | Pakiet |
|---|-----|-----------|-----------|--------|
| 1 | **Operation** — rekord zadania (UID, owner, status, traceback) | durable | Postgres | 2 — `django-background-operations` |
| 2 | **Progress** — live `%` + komunikat biegnącej operacji | transient | Redis | 2 — `django-background-operations` |
| 3 | **Live signal** — ulotny event „op X się zmieniła/skończyła, odśwież/toastnij" | ulotny | websocket (channels) | 3 — `django-live-messages` (z `channels_broadcast`) |
| 4 | **Standing notification** — trwały komunikat „skończyło się, wejdź tu", zostaje aż przeczytany/odrzucony | durable | DB | 1 — `messages-extends` *(już masz)* |

Kluczowe rozróżnienia, które się myliły:
- **Progress (2) ≠ Operation (1).** Pasek to ulotna projekcja, nie rekord.
- **Live signal (3) ≠ Standing notification (4).** Websocket „skończyło
  się" to ulotny sygnał liveness. Trwały komunikat „skończyło się, oto
  link" to osobny, durable byt — i to jest dokładnie `messages_extends`.
- Live progress (2/3) to **opcjonalna szybka ścieżka**. Trwały komunikat
  (4) to **kręgosłup**, który działa nawet gdy user nigdy nie widział
  paska (zamknął okno).

## Dwie osie powiadamiania (to się myliło najbardziej)

Powiadomienia mają **dwie niezależne osie** — myliliśmy je, bo zwykle
patrzy się tylko na jedną:

**Oś 1 — KIEDY: w trakcie vs po.**
- *W trakcie procesu* — „leci, jest na 40%". Z natury ulotne (#2/#3).
  Sens ma tylko dla obecnych. Po zakończeniu znika.
- *Po procesie* — „skończyło się". To moment, w którym rodzi się
  trwały byt #4.

**Oś 2 — CZY WYMAGA DECYZJI (dotyczy tylko powiadomień „po").**
Trwałość komunikatu „po" **nie** wynika z ważności, tylko z tego, czy
user musi coś **postanowić**:
- *Informacyjny* → **znika sam**. „Raport gotowy", „eksport zakończony".
  User nie musi nic robić; FYI. Toast auto-dismiss / poziom nie-persistent.
- *Decyzyjny / call-to-action* → **zostaje na stałe, aż user podejmie
  decyzję.** „Import skończył się po 3 h — co robimy dalej?". To nie jest
  „FYI", to punkt decyzyjny: user wraca po godzinach, widzi wynik i
  **wybiera** następny krok. Komunikat musi przeżyć zamknięcie okna,
  reload, wylogowanie — i zniknąć dopiero, gdy decyzja zapadnie (nie samo
  „przeczytanie"). Poziom `*_PERSISTENT` w `messages_extends`; ewentualnie
  niosący akcje/linki następnego kroku, nie tylko „zobacz wynik".

Konsekwencja projektowa: emisja powiadomienia „po" bierze **flagę**
(`persistent: bool` lub wręcz typ: `informational` / `decision_required`).
To konsument operacji decyduje przy definicji — bo tylko on wie, czy jego
import kończy się decyzją, czy samym faktem. Domyślnie warto: sukces
zwykłej operacji = informacyjny (znika), błąd / wynik wymagający akcji =
decyzyjny (zostaje).

## Co już mamy i reużywamy (nie piszemy od zera)

- **`messages_extends`** (django-messages-extends 0.6.3) — trwałe
  komunikaty. `MESSAGE_STORAGE = messages_extends.storages.FallbackStorage`
  (`settings/base.py:807`). Poziomy `*_PERSISTENT` (`INFO_PERSISTENT`…)
  → model `Message` (user, body, `read`, level). **`read` jest
  auto-ustawiane**, gdy user odwiedzi URL z treści komunikatu —
  `NotificationsMiddleware` (`bpp/middleware.py:374`). Czyli „skończyło
  się, wejdź tu" + samo-oznaczenie-przeczytane-po-wejściu **już działa**.
  To jest byt #4. Nową apkę tylko **podpinamy** do tego na zakończeniu
  operacji.
- **`channels` / `channels_broadcast`** — websocket. Byt #3.
- **`toastify`** (`channels_broadcast/js/notifications-toastify.js`) —
  wspiera sticky toasty. Reużyć zamiast pisać widget.
- **Redis** (channels-redis już w stacku) — byt #2.

## Algorytm notyfikacji (rdzeń decyzji)

User uruchamia coś długo działającego i zachowuje się na 3 sposoby.
Macierz „co pokazujemy":

| Zachowanie usera | W trakcie (running) | Po zakończeniu (finished) |
|---|---|---|
| **(1) zamyka okno, idzie precz** | nic live (brak strony) — OK | **standing notification #4** (`messages_extends`): zobaczy przy następnym wejściu/zalogowaniu. *(opcjonalnie kiedyś: e-mail po N h nieprzeczytania)* |
| **(2) zostawia okno otwarte (chce czekać)** | progress **w głównym miejscu** (user wyraźnie czeka) — live #3 + `%` z Redisa #2 | sygnał #3 „skończone" → redirect/zaproszenie na stronę wyniku; **+** standing #4 |
| **(3) okno otwarte, ale nawiguje po innych stronach** | progress w **rozwijanej szufladzie** (globalny widget, przeżywa zmianę stron) — live #3 + `%` #2 | toast #3 „skończyło się, zobacz wynik"; **+** standing #4 zostaje aż przeczytany |

**Unifikacja:** zakończenie operacji **zawsze** tworzy standing
notification #4 (`messages_extends`) — niezależnie od scenariusza. Live
progress (#2/#3) to tylko ozdoba dla obecnych. Dzięki temu „zamknął okno"
i „patrzył na pasek" zbiegają się w jednym trwałym komunikacie.

### Zasada, która sprawia że „websockety zostają" jest bezpieczne

**Websocket = ulotny sygnał „odśwież/pokaż", NIE rura z danymi. Źródło
prawdy: DB (#1, #4) + Redis (#2).** Jeśli przeglądarka przegapi event
(offline, uśpiona, proxy ubił socket), **samo się leczy**: przy
następnym wejściu / reconnect / `visibilitychange→visible` klient
pobiera aktualny stan (otwarte operacje + nieprzeczytane komunikaty)
z endpointu. Websocket może być stratny bez psucia poprawności — to
różnica względem dawnego „websocket jako jedyny kanał".

### Synchronizacja między oknami (to „bardziej ludzkie" WS)

Potwierdzenie/przeczytanie komunikatu w jednym oknie → zapis w DB
(`Message.read=True`) **+** broadcast eventu #3 do grupy `user-{id}` →
pozostałe okna usera chowają toast/banner. Ack jest serwerowy, więc
multi-tab dedupuje się sam.

## Otwarte decyzje (do rozstrzygnięcia, gdy wrócimy)

- **Anulowanie biegnącej operacji** — naturalne przy paskach (revoke
  taska + `state=cancelled`). Na razie odłożone; zostawić `cancelled_on`
  w modelu na zapas.
- **`perform()` w transakcji?** — z progressem w Redisie *można*
  transakcyjnie, ale importy często wolą commity per-batch. Domyślnie
  bez wymuszania, konsument decyduje (override).
- **Eventy WS: thin czy fat?** — rekomendacja: **thin** („coś się
  zmieniło, refetchuj listę") + autorytatywny fetch. Ewentualnie hybryda:
  event niesie `uid`+`state` do tekstu toastu, ale dashboard i tak
  refetchuje. Unikać dwóch źródeł prawdy.
- **Grupa WS na gołym `channels` czy przez `channels_broadcast`?** —
  dla reusability: gołe `channels`, grupa `user-{id}` przez
  `AuthMiddlewareStack`. `channels_broadcast` kusi szybkością, ale wiąże
  apkę z wewnętrznym pakietem (psuje ekstrahowalność).
- **Semantyka „przeczytane/ack"** — „toast się pokazał" czy „user
  kliknął"? Dziś `messages_extends` robi: „odwiedził URL z treści" =
  read. Rozważyć spójność z tym.

## Łatwo zapomnieć (z brainstormu)

- **Rozdziel częstotliwość `set_progress` (często → Redis) od eventów WS
  (throttlowane: max co ~1-2 s albo co Δ5%).** Inaczej WS zaleje progress-
  spamem. Pasek `%` klient czyta z Redisa/endpointu, nie z każdego eventu.
- **Sticky toast „do potwierdzenia" to wiersz w DB** (#4), re-serwowany
  przy reloadzie — nie ulotny toast. Auto-znikające mogą być ulotne.
- **Live `%` jest ulotne** (Redis): worker padnie → `%` znika, ale wiersz
  #1 mówi „started, not finished" → pokazujesz „w toku". Nieszkodliwe.
- **TTL + sprzątanie kluczy Redis** na finiszu operacji.
- **Wyścig task-vs-commit** → zostaje `transaction.on_commit` + retry
  (jak w dzisiejszym `tasks.py`).
- **Owner-scoping** endpointu `/moje-operacje/` i grupy WS (`owner =
  request.user`).
- **Reconnect + refetch-on-focus** (~10 linii JS) — konsekwencja zasady
  o stratnym WS.

## Świadomie odłożone

- **Eskalacja e-mail** (nieprzeczytane po 2-3 h / user offline) — model
  dostanie `acknowledged_on`/`emailed_on`, więc beat-task dołożymy później
  bez migracji-rewolucji. **Nie w pierwszym wydaniu.**
- Fizyczna ekstrakcja pakietów (2 i 3) do osobnych repo/PyPI — dopiero
  gdy stabilne i pojawi się drugi konsument spoza BPP.

## Gdy wrócimy — proponowana kolejność (wg pakietów)

- **SP1 — Pakiet 2 (`django-background-operations`):** `Operation`
  (+ `label`, `acknowledged_on`, `cancelled_on`), tracker Redis
  (`set/get_progress`), endpoint statusu `/moje-operacje/` (JSON),
  szuflada/widget (htmx + toastify), sygnał `operation_finished`,
  `test_app`. **Samodzielny — nie wymaga websocketów** (status przez
  polling API). Zabija push-progress `long_running` dla części
  „śledzenie".
- **SP2 — Pakiet 3 (`django-live-messages`):** transport live nad
  `messages-extends` (push + sync zamknięcia między kartami), ewolucja
  `channels_broadcast`. **+** klej BPP-owy: `operation_finished` →
  `live_messages.send(...)`. Dopiero tu wchodzą websockety.
- **SP3 — eskalacja e-mail** (ack + beat-task) — nad messages-extends/
  operacjami.
- **SP4 — sprzątanie `pbn_import`** (jego własny consumer websocket) —
  ale **uwaga na fork**: pełne zejście z daphne jest **wykluczające się**
  z adopcją Pakietu 3 (live-messages stoi na websocketach → daphne
  zostaje). Decyzja „websockety zostają" (przyjęta) oznacza, że daphne
  zostaje, a migracja `pbn_import` to zwykłe ujednolicenie kanałów, nie
  usunięcie ASGI. Czysto-pollingowy wariant (drop daphne, brak live-push)
  to alternatywa, której świadomie nie wybieramy.

Każdy SP własny cykl spec → plan → implementacja.
