# Notatka na przyszłość: `django-background-operations`

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

## Wizja: nowa apka `django-background-operations`

Nowa apka (nie przebudowa `long_running` w miejscu — przy 12 konsumentach
zbyt ryzykowne). Konsumenci migrują pojedynczo; `long_running` zostaje aż
się opróżni. Apka **bpp-free od dnia zero** (`owner =
settings.AUTH_USER_MODEL`), bo nazwa pachnie reusable — kandydat do
ekstrakcji jak `pbn_client`.

Zawiera:
- `Operation` (durable): UID (UUID), owner, start/koniec, status,
  traceback, `label`/`title` (ludzka nazwa do toastu/szuflady).
- `set_progress` / `get_progress` przez **Redis** (transient, poza
  transakcją — zapis natychmiast widoczny dla czytelników).
- `test_app` w środku: (a) przykładowy `Operation`-subclass + trywialny
  task „licz do 100" pod testy integracyjne, (b) uruchamialna strona
  demo z paskiem.

## NAJWAŻNIEJSZE: taksonomia pojęć (to się zlewało)

Cztery **różne** byty. Mieszanie ich było źródłem zamętu:

| # | Byt | Czas życia | Gdzie żyje | Status w projekcie |
|---|-----|-----------|-----------|--------------------|
| 1 | **Operation** — rekord zadania (UID, owner, status, traceback) | durable | Postgres | do zbudowania (nowa apka) |
| 2 | **Progress** — live `%` + komunikat biegnącej operacji | transient | Redis | do zbudowania (`set/get_progress`) |
| 3 | **Live signal** — ulotny event „op X się zmieniła/skończyła, odśwież/toastnij" | ulotny | websocket (channels) | mamy `channels_broadcast` |
| 4 | **Standing notification** — trwały komunikat „skończyło się, wejdź tu", zostaje aż przeczytany/odrzucony | durable | DB | **JUŻ MAMY: `messages_extends`** |

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
- Fizyczna ekstrakcja apki do osobnego repo/PyPI — dopiero gdy stabilna.

## Gdy wrócimy — proponowana dekompozycja

- **SP1** — silnik + globalny delivery: `Operation` (+ `label`,
  `acknowledged_on`, `cancelled_on`), tracker Redis (`set/get_progress`),
  endpoint `/moje-operacje/` (JSON), globalna szurada/widget (htmx +
  toastify), thin eventy WS, podpięcie zakończenia do `messages_extends`
  (#4), sync ack między oknami, `test_app`. Zabija push-progress
  `long_running`.
- **SP2** — eskalacja e-mail (ack + beat-task).
- **SP3** — decommission daphne: migracja `pbn_import` (własny consumer),
  usunięcie `channels`/daphne — tylko jeśli realnie chcemy zejść z ASGI.

Każdy SP własny cykl spec → plan → implementacja.
