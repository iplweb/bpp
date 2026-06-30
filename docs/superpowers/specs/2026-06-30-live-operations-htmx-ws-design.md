# `live_operations` — reusable framework długich operacji (WebSocket + HTMX, bez pollingu)

- **Data:** 2026-06-30
- **Status:** spec (do akceptacji)
- **Gałąź:** `feat/live-operations`
- **Następca:** `long_running` (koegzystencja, patrz §11)
- **Pilotaż:** `import_punktacji_zrodel` (FD#388), potem migracja kolejnych

> Nazwa robocza: **`live_operations`** (alt.: `liveops`, `long_running2`).
> Do potwierdzenia — patrz §13.

---

## 1. Motywacja — co boli w obecnym `long_running`

Obecny framework działa, ale ma trzy strukturalne wady (zaobserwowane przy
FD#388):

1. **Nawigacja przegrywa wyścig z ACK.** Po zakończeniu serwer wysyła trwałą
   notyfikację `{url:".."}`; klient kolejkuje ACK na sockecie i **natychmiast**
   robi `window.location.href`. Strona się wyładowuje, ACK nie dochodzi,
   notyfikacja zostaje `acknowledged=False`. Strona wyników subskrybuje ten
   sam kanał → `on_connect` odtwarza ją znowu → `goTo` → **ping-pong** między
   stronami, aż ACK przypadkiem wskoczy.
2. **Reload niszczy socket.** Każde przeładowanie (np. awaryjny `meta-refresh`,
   przejście router→details→results) rozłącza WS, wymusza reconnect i ponowne
   odtworzenie nieacknowledge'owanych zdarzeń. Reload i WS walczą ze sobą.
3. **„Upierdliwe" UID kanału.** Deweloper ręcznie żongluje:
   `asgi_channel_name = str(pk)`, `extraChannels=[self.object.pk]` w
   `get_context_data`, `redirect_prefix`, mapowanie stanów na sufiksy URL.
   Dużo ceremonii, by powiedzieć „ta operacja → ta strona".
4. **Model „strumień zdarzeń + ACK"** jest z natury kruchy: zdarzenie
   wysłane raz, musi być odebrane i potwierdzone. Każde zgubienie wymaga
   replay i bookkeepingu.

Cel `live_operations`: **płynna, błyskawiczna aktualizacja stanu po
WebSockecie, podmiana treści in-place przez HTMX (bez nawigacji i bez
pollingu), oraz ergonomiczne API**, w którym deweloper operuje na obiekcie
`progress`/operacji, a nie na identyfikatorach kanałów.

---

## 2. Zasady projektowe (fundament)

1. **Projekcja stanu, nie strumień zdarzeń.** Operacja ma **stan**
   (status, procent, log, wynik). Po sockecie płyną **fragmenty HTML
   odzwierciedlające bieżący stan**, wstawiane out-of-band przez HTMX wg
   `id`. Swap po `id` jest **idempotentny** → ponowne wysłanie tego samego
   stanu nic nie psuje. To eliminuje cały taniec ACK/replay/ping-pong.
2. **Strona stoi, treść się zmienia.** Żadnej nawigacji w trakcie. Socket
   pozostaje otwarty przez cały cykl: start → postęp → wynik. Wynik
   **podmienia region** na tej samej stronie (in-place), nie przekierowuje.
3. **Push, nie polling.** WebSocket dostarcza aktualizacje natychmiast.
   Zero `setInterval`, zero `hx-trigger="every 3s"`. (Polling istnieje
   wyłącznie jako opcjonalny *degradacyjny* fallback, patrz §7.4.)
4. **Resync na (re)connect.** Po połączeniu serwer wysyła **pełny bieżący
   stan** (snapshot wszystkich regionów). Reconnect po zerwaniu = strona
   natychmiast dogania rzeczywistość. Bo swapy są idempotentne — to bezpieczne.
5. **Ergonomia ponad ceremonię.** Deweloper pisze `run(self, p)` i woła
   `p.status(...)`, `p.track(...)`, `p.log(...)`, `p.result(...)`. Kanał,
   wiązanie strony, throttling, snapshot — robi framework. Nigdzie nie
   przekazuje się ręcznie UID-a strony ani kanału.

---

## 3. Architektura — komponenty

```
┌──────────────────────────────────────────────────────────────┐
│  Przeglądarka (jedna, stojąca strona operacji)               │
│   <div id="op-<pk>" hx-ext="ws" ws-connect="/live/<pk>/">    │
│     <div id="op-status">…</div>      ← regiony OOB-swap       │
│     <div id="op-progress">…</div>                            │
│     <div id="op-log">…</div>                                 │
│     <div id="op-result">…</div>                              │
│   </div>                                                      │
└───────────────▲───────────────────────────┬─────────────────┘
                │ HTML fragments (hx-swap-oob)│ (brak nawigacji)
                │                             │
┌───────────────┴─────────────────────────────────────────────┐
│  LiveOperationConsumer (Django Channels, ASGI)               │
│   - autoryzacja: właściciel operacji / token                 │
│   - on connect: wyślij snapshot stanu (wszystkie regiony)    │
│   - subskrypcja grupy "liveop.<pk>"                          │
└───────────────▲───────────────────────────┬─────────────────┘
                │ group_send(render fragm.)  │
┌───────────────┴─────────────────────────────────────────────┐
│  Worker Celery: LiveOperation.run(self, p)                   │
│   p = Progress(operation)                                     │
│   p.status / p.percent / p.track / p.log / p.swap / p.result │
│   każda metoda: zapis stanu (DB) + group_send(fragment HTML) │
└──────────────────────────────────────────────────────────────┘
```

Komponenty:
- **`LiveOperation`** (abstrakcyjny model) — stan + cykl życia + `run()`.
- **`Progress`** — uchwyt wstrzykiwany do `run(self, p)`; cienkie, przyjazne
  API do raportowania stanu. Nie zna kanałów — zna operację.
- **`LiveOperationConsumer`** — jeden consumer Channels; autoryzuje, wysyła
  snapshot na connect, transmituje fragmenty.
- **Klient** — oficjalne rozszerzenie **htmx `ws`** (`hx-ext="ws"`) +
  drobny shim do statusu połączenia. Bez własnego protokołu JSON.
- **Widoki/mixiny** — `Create`, `Live` (strona operacji), `List`; brak
  osobnych router/details/results jako oddzielnych nawigacji.
- **Fragmenty** — małe szablony regionów (`_status.html`, `_progress.html`,
  `_log.html`, `_result.html`) renderowane i wstawiane OOB.

---

## 4. Developer API (sedno ergonomii)

### 4.1 Definicja operacji

```python
from live_operations.models import LiveOperation
from live_operations.progress import Progress


class ImportPunktacji(LiveOperation):
    plik = models.FileField(upload_to="protected/import_punktacji/")
    rok = YearField(null=True, blank=True)

    # Deweloper pisze TYLKO to. Bez UID, bez kanałów, bez sufiksów URL.
    def run(self, p: Progress):
        p.status("Wczytuję plik…")
        czasopisma = wczytaj_plik_jcr(self.plik.path).czasopisma

        for cz in p.track(czasopisma, label="Dopasowuję źródła"):
            wynik = dopasuj_i_zapisz(cz, self)
            p.log(f"{cz.nazwa}: {wynik}")          # strumieniowy raport (tqdm-like)

        # finał — podmiana regionu wyników IN-PLACE (bez nawigacji):
        p.result("import_punktacji/_wyniki.html", {"operacja": self})
```

### 4.2 `Progress` — pełne API

| Metoda | Działanie | Region docelowy |
|---|---|---|
| `p.status(text, level="info")` | krótki komunikat stanu | `#op-status` |
| `p.percent(value)` | ustaw pasek (0–100) | `#op-progress` |
| `p.track(iterable, total=None, label=None, unit="szt.")` | **generator**: iteruje i automatycznie aktualizuje pasek + ETA (tqdm-style), z throttlingiem | `#op-progress` |
| `p.log(line)` | dopisz linię do strumieniowego logu (raport tekstowy) | `#op-log` (append) |
| `p.swap(selector, template, context, mode="innerHTML")` | dowolny region: renderuj fragment i wstaw OOB | dowolny `id` |
| `p.html(selector, html, mode="innerHTML")` | jak wyżej, surowy HTML | dowolny `id` |
| `p.result(template, context)` | finalizacja sukcesem: podmień `#op-result`, oznacz operację jako zakończoną, zatrzymaj pasek | `#op-result` |
| `p.error(message)` | finalizacja błędem: pokaż komunikat + „Uruchom ponownie" | `#op-result` |
| `p.redirect(url)` | *opcjonalnie* nawiguj (gdy ktoś naprawdę chce zmienić stronę) | — |

Zasady wbudowane:
- **Throttling**: `p.percent`/`p.track` koalescjonuje wysyłki (domyślnie
  ≤ ~10/s i/lub co ≥1% zmiany) — „błyskawicznie", ale bez zalewania socketu.
- **Idempotencja**: status/percent/result/swap to swap po `id` → wielokrotne
  wysłanie tego samego stanu jest nieszkodliwe (kluczowe przy resync).
- **Log** jest *przyrostowy* (append). Dla resync (§7.3) log jest częścią
  stanu i przy reconnect odsyłany w całości (lub jako „ogon + licznik").

### 4.3 Co znika z DX (vs `long_running`)

- ❌ `asgi_channel_name`, `extraChannels=[pk]`, `redirect_prefix`,
  `STATE_TO_SUFFIX_MAP`, `get_url("results")`, ręczne notyfikacje.
- ✅ Zostaje: pole(a) modelu + jedna metoda `run(self, p)`.

---

## 5. Wiązanie strony z operacją (koniec „upierdliwego UID")

- Strona operacji renderuje się przez `LiveOperationView` (mixin), który
  **sam** wstawia kontener:
  ```django
  {% live_operation operacja %}   {# templatetag #}
    {# rozwija się do: #}
    <div id="op-{{ operacja.pk }}"
         hx-ext="ws"
         ws-connect="{% url 'live_operations:ws' operacja.pk %}">
      {% include "live_operations/_regions.html" %}
    </div>
  ```
- Deweloper **nie** przekazuje UID-a. Wiązanie „ta operacja ↔ ta strona"
  wynika z obiektu `operacja` podanego do templatetagu. Kanał = pochodna
  `pk` (ukryta w consumerze).
- „Konkretna strona / region": dzięki `p.swap(selector, …)` deweloper
  aktualizuje dowolny wycinek tej strony — adresuje **selektorem CSS**,
  a nie identyfikatorem strony.

---

## 6. Protokół transportu (WS ↔ HTMX)

- Transport: **Django Channels** (ASGI) + oficjalne **htmx `ws`**.
- Serwer wysyła **fragmenty HTML** z atrybutem `hx-swap-oob`:
  ```html
  <div id="op-progress" hx-swap-oob="true">
    <div class="progress"><div class="progress-meter" style="width:42%"></div></div>
    <small>42% · 57/136 · ~8 s</small>
  </div>
  ```
  HTMX rozszerzenie `ws` traktuje każdą wiadomość jak odpowiedź i robi
  OOB-swap elementów po `id`. **Zero własnego JS** do swapów.
- Append (log) przez `hx-swap-oob="beforeend:#op-log"`:
  ```html
  <div hx-swap-oob="beforeend:#op-log"><div class="log-line">LANCET: zapisano</div></div>
  ```
- Drobny shim JS tylko do **wskaźnika połączenia** (online/reconnecting) i
  ewentualnego zdarzenia `liveop:done` (np. odtworzenie focus/scroll).

---

## 7. Niezawodność (to, co dziś kruche)

### 7.1 Brak nawigacji = ACK zbędny
Skoro finał to OOB-swap regionu `#op-result` (a nie `window.location`),
strona się nie wyładowuje, socket żyje, kolejne wiadomości docierają.
Znika cała klasa wyścigów „nawigacja vs potwierdzenie".

### 7.2 Idempotentny snapshot zamiast ACK
Nie potrzebujemy `acknowledged` ani replay-po-jednym. **Stan operacji jest
źródłem prawdy** (DB), a fragmenty są jego deterministyczną projekcją.

### 7.3 Resync na (re)connect
`LiveOperationConsumer.connect()`:
1. autoryzuj (właściciel operacji / token),
2. wyślij **snapshot**: aktualny status, percent, **cały log**, oraz —
   jeśli `finished` — fragment wyniku.
Dzięki idempotencji swapów strona po reconnect natychmiast pokazuje
bieżący stan, niezależnie od tego, ile wiadomości „przegapiła". To
zastępuje kruchy mechanizm „trwała notyfikacja + ACK".

> Log: by uniknąć duplikacji przy append, log trzymamy w stanie operacji
> (lista linii lub licznik). Live = `beforeend` pojedynczej linii; reconnect
> = `innerHTML` całego logu. Dla bardzo długich logów: „ogon N linii +
> licznik pominiętych".

### 7.4 Degradacja bez ASGI (opcjonalna)
Gdy WS nie wstaje (brak Daphne/channel-layer), kontener może mieć
*opcjonalny* atrybut `hx-trigger="every 3s"` na endpoint snapshotu
(ten sam fragment co po WS-connect). To **pull-fallback** — lekki fetch
fragmentu, nie reload strony. Domyślnie wyłączony; włączany flagą,
gdy deployment nie ma ASGI. (Cel główny to WS; to tylko siatka.)

---

## 8. Bezpieczeństwo

- **Autoryzacja kanału = właściciel operacji.** Consumer w `connect()`
  sprawdza `scope["user"] == operation.owner` (lub uprawnienie/grupę),
  inaczej `close()`. Brak dostępu do cudzych operacji.
- **Token subskrypcji** (jak w `channels_broadcast.security`) — podpisany,
  krótkotrwały, wiążący użytkownika z konkretną operacją; chroni przed
  podsłuchaniem cudzego kanału po samym `pk`.
- **Brak wykonania dowolnego HTML od klienta** — klient tylko odbiera; nie
  wysyła swapów. Wiadomości serwera renderowane z zaufanych szablonów,
  z autoescapingiem.
- **CSRF**: WS nie używa CSRF; akcje mutujące (start/restart/zatwierdź) idą
  zwykłym POST-em z tokenem, nie po WS.

---

## 9. Widoki, URL-e, szablony

- `CreateLiveOperationView` — formularz; po zapisie dispatch zadania Celery
  i **redirect na stronę operacji** (jedyna nawigacja w całym cyklu).
- `LiveOperationView` — **stojąca** strona operacji: regiony +
  `{% live_operation op %}`. Tu dzieje się wszystko (postęp → wynik
  in-place). Brak osobnych „details" i „results" jako oddzielnych URLi…
  - …ale dla **deep-linku / powrotu** wynik jest też dostępny pod GET
    (ta sama strona, która dla zakończonej operacji renderuje od razu
    fragment wyniku w `#op-result`). Czyli odświeżenie strony zakończonej
    operacji = od razu wyniki, bez czekania.
- `LiveOperationListView` — lista operacji użytkownika (jak dziś).
- WS: `path("live/<uuid:pk>/", LiveOperationConsumer.as_asgi())`.
- Szablony regionów: `live_operations/_regions.html`, `_status.html`,
  `_progress.html`, `_log.html`, `_result.html` (deweloper nadpisuje
  `_result.html` per-aplikacja albo podaje własny w `p.result(...)`).

---

## 10. Model danych

```python
class LiveOperation(models.Model):       # abstrakcyjny
    id = UUIDField(primary_key=True, default=uuid4)
    owner = FK(AUTH_USER_MODEL, CASCADE)

    created_on = DateTimeField(auto_now_add=True)
    started_on = DateTimeField(null=True, blank=True)
    finished_on = DateTimeField(null=True, blank=True)
    finished_successfully = BooleanField(default=False)
    traceback = TextField(null=True, blank=True)

    # Stan do projekcji/resync:
    status_text = CharField(max_length=255, blank=True, default="")
    percent = PositiveSmallIntegerField(default=0)
    log = JSONField(default=list)          # lista linii (lub osobny model wierszy)
    result_html = TextField(blank=True, default="")   # zrenderowany fragment wyniku

    class Meta:
        abstract = True
        ordering = ["-created_on"]

    # do nadpisania przez dewelopera:
    def run(self, p): raise NotImplementedError

    # framework: task_run() opakowuje run() w transakcję + obsługę błędów,
    # zapisuje stan, woła p.* (które robią group_send fragmentów).
```

- **Stan operacji jest trwały** → snapshot na reconnect jest możliwy bez
  żadnego ACK.
- `log` jako `JSONField` dla prostoty; dla dużych raportów — osobny model
  `LiveOperationLogLine(parent, nr, text)` (decyzja §13).

---

## 11. Relacja do istniejącego `long_running`

- **Koegzystencja.** `live_operations` to nowa, niezależna app. `long_running`
  zostaje dla istniejących konsumentów (`import_list_if`,
  `import_list_ministerialnych`, `rozbieznosci`, raporty…) do czasu migracji.
- **Pilotaż:** przepisać `import_punktacji_zrodel` na `live_operations`
  (mały, świeży, dobrze otestowany konsument; FD#388). Usunąć wtedy
  awaryjny `meta-refresh`.
- **Migracja stopniowa:** kolejni konsumenci przechodzą pojedynczo. Gdy
  ostatni zejdzie z `long_running`, można go usunąć.
- **Wspólne klocki:** część `channels_broadcast` (consumer bazowy, security,
  token) da się reużyć/rozszerzyć zamiast pisać od zera — do oceny w planie.

---

## 12. Testy

- **Jednostkowe `Progress`:** `track()` liczy procenty/ETA i throttluje;
  `log()` dopisuje; `result()` ustawia `finished` + `result_html`; każda
  metoda renderuje poprawny fragment z `hx-swap-oob`.
- **Consumer (pytest + channels `WebsocketCommunicator`):**
  - connect nieautoryzowany → odrzucony;
  - connect właściciela → dostaje snapshot (status/percent/log/wynik);
  - po `p.percent(...)` klient dostaje fragment `#op-progress`;
  - reconnect w połowie → dostaje aktualny snapshot (idempotencja);
  - operacja zakończona przed connectem → snapshot od razu zawiera wynik
    (klasyczny przypadek „skończyło się nim strona wstała").
- **Integracyjne (Playwright, opcjonalnie):** strona stoi, pasek rośnie,
  log dopisuje, wynik pojawia się in-place bez przeładowania (sprawdzić, że
  `window.performance` nie notuje nawigacji).
- **Degradacja:** z wyłączonym WS i włączonym pull-fallback strona i tak
  dochodzi do wyniku (fetch fragmentu, bez reloadu).

---

## 13. Otwarte decyzje (do rozstrzygnięcia przed planem)

1. **Nazwa app**: `live_operations` / `liveops` / `long_running2`?
2. **Zakres v1**: tylko pilotaż w `import_punktacji_zrodel`, czy od razu
   wspólna baza pod migrację wszystkich?
3. **Reużycie `channels_broadcast`**: rozszerzyć istniejący consumer/security
   czy napisać dedykowany `LiveOperationConsumer`?
4. **Log storage**: `JSONField` (proste) vs osobny model wierszy (skalowalne,
   filtrowalne — jak dziś `Wiersz…` w importerach).
5. **htmx `ws` ext**: dociągnąć oficjalne rozszerzenie do bundla (zależność
   front-endowa) — czy jest już w projekcie? (do sprawdzenia w planie).
6. **Pull-fallback**: czy w ogóle go chcemy w v1, czy zakładamy, że produkcja
   ma ASGI (Daphne już jest dla `channels_live_server`/testów Playwright).
7. **Wynik jako osobny URL**: czy oprócz in-place trzymać też kanoniczny
   GET wyników (deep-link) — rekomendacja: tak (§9).

---

## 14. Dlaczego to „fajnie śmiga" (podsumowanie)

- **Błyskawicznie**: push po WS + OOB-swap = aktualizacja w momencie zdarzenia,
  bez 3-sekundowego pollingu i bez reloadów.
- **Niezawodnie**: stan w DB + idempotentny snapshot na (re)connect =
  brak zgubionych sygnałów, brak ping-pongu, brak wyścigu z ACK.
- **Ergonomicznie**: deweloper pisze `run(self, p)` i woła `p.status / p.track
  / p.log / p.result`. Zero UID-ów, zero kanałów, zero sufiksów URL.
- **Uniwersalnie**: `p.swap(selector, …)` pozwala aktualizować dowolny region
  dowolnej strony — pasek, log-tqdm, podgląd, wynik — czym tylko chcesz.
