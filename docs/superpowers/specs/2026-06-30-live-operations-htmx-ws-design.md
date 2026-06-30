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

        # finał — podmiana regionu wyników IN-PLACE (bez nawigacji).
        # BEZ podawania nazwy szablonu: framework sam wylicza go z nazwy
        # klasy → import_punktacji_zrodel/import_punktacji_result.html
        # (patrz §4.4). Kontekst opcjonalny — domyślnie {object, operation}.
        p.result()
        # albo z dodatkowym kontekstem: p.result(podsumowanie=stats)
```

### 4.2 `Progress` — pełne API

| Metoda | Działanie | Region docelowy |
|---|---|---|
| `p.status(text, level="info")` | krótki komunikat stanu | `#op-status` |
| `p.percent(value)` | ustaw pasek (0–100) | `#op-progress` |
| `p.track(iterable, total=None, label=None, unit="szt.")` | **generator**: iteruje i automatycznie aktualizuje pasek + ETA (tqdm-style), z throttlingiem | `#op-progress` |
| `p.log(line)` | dopisz linię do strumieniowego logu (raport tekstowy) | `#op-log` (append) |
| `p.swap(selector, name=None, **context)` | dowolny region: renderuj fragment (auto-nazwa `<app>/<klasa>_<name>.html` albo jawnie) i wstaw OOB | dowolny `id` |
| `p.html(selector, html, mode="innerHTML")` | jak wyżej, surowy HTML | dowolny `id` |
| `p.result(context=None, **extra)` | finalizacja sukcesem: render **auto-wyliczonego** szablonu wyniku (§4.4), podmień `#op-result`, oznacz operację jako zakończoną, zatrzymaj pasek | `#op-result` |
| `p.error(message)` | finalizacja błędem: pokaż komunikat + „Uruchom ponownie" | `#op-result` |
| `p.check_cancelled()` | zgłasza `OperationCancelled`, jeśli użytkownik anulował (patrz §4.5); wołaj w pętli | — |
| `with p.stage(name):` | context manager etapu — rysuje stepper, skopuje postęp/log do bieżącego etapu (§16.1) | `#op-stages` + `#op-progress` |
| `p.chain_to(next_op)` | finalizuje bieżącą i montuje następną operację **in-place, bez reloadu** (§16.2) | `#op-root` |
| `p.redirect(url)` | *opcjonalnie* nawiguj (gdy ktoś naprawdę chce zmienić stronę) | — |

Domyślnie **nigdzie nie podaje się nazwy szablonu** — `p.result()` i fragmenty
regionów wyliczają nazwy z klasy operacji (§4.4). Jawny szablon jest możliwy,
ale to wyjątek, nie norma.

Zasady wbudowane:
- **Throttling**: `p.percent`/`p.track` koalescjonuje wysyłki (domyślnie
  ≤ ~10/s i/lub co ≥1% zmiany) — „błyskawicznie", ale bez zalewania socketu.
- **Idempotencja**: status/percent/result/swap to swap po `id` → wielokrotne
  wysłanie tego samego stanu jest nieszkodliwe (kluczowe przy resync).
- **Log** jest *przyrostowy* (append). Dla resync (§7.3) log jest częścią
  stanu i przy reconnect odsyłany w całości (lub jako „ogon + licznik").

### 4.3 Co znika z DX (vs `long_running`)

- ❌ `asgi_channel_name`, `extraChannels=[pk]`, `redirect_prefix`,
  `STATE_TO_SUFFIX_MAP`, `get_url("results")`, ręczne notyfikacje,
  **ręczne nazwy szablonów** (§4.4).
- ✅ Zostaje: pole(a) modelu + jedna metoda `run(self, p)`.

### 4.4 Auto-derivacja szablonów + „duży" host page (konwencja > konfiguracja)

Deweloper **nie podaje nazw szablonów**. Framework wylicza je z klasy
operacji (`app_label` + snake_case nazwy klasy). Dla
`class ImportPunktacji(LiveOperation)` w aplikacji
`import_punktacji_zrodel`:

| Rola | Nazwa wyliczona automatycznie | Fallback (z pakietu) |
|---|---|---|
| **Host page** („duży" plik, na którym renderują się fragmenty) | `import_punktacji_zrodel/import_punktacji.html` | `live_operations/operation.html` |
| **Fragment wyniku** (`p.result()`) | `import_punktacji_zrodel/import_punktacji_result.html` | `live_operations/_result.html` |
| Fragment `p.swap(sel, name="foo")` | `import_punktacji_zrodel/import_punktacji_foo.html` | — |
| Status / pasek / log | — | `live_operations/_status.html`, `_progress.html`, `_log.html` |

Reguły:
- **Snake_case z CamelCase**: `ImportPunktacji` → `import_punktacji`
  (helper `class_to_snake`). `app_label` z `Model._meta.app_label`.
- **Override punktowy** (wyjątek, nie norma): atrybut klasy
  `result_template_name = "..."`, `host_template_name = "..."`, albo
  argument `p.result(template="...")` / `p.swap(..., template="...")`.
- **Host page = jeden „duży" plik per operacja.** Domyślnie deweloper nie
  musi go pisać — pakiet ma `live_operations/operation.html`, który
  `{% extends %}` bazowy szablon projektu i renderuje regiony przez
  `{% live_operation op %}`. Gdy chce własny layout, tworzy
  `import_punktacji_zrodel/import_punktacji.html` (auto-wykrywany) i tam
  rozkłada regiony / dodatkowe sekcje. To realizuje „gdzieś jest duży plik
  HTML, na którym te fragmenty się renderują".
- **Domyślnie wszystko to fragmenty.** Regiony (`#op-status/#op-progress/
  #op-log/#op-result`) są małymi fragmentami wstawianymi OOB w host page.
  Deweloper nadpisuje tylko te, które chce — zwykle sam `_result`.

Konfigurowalny prefiks szablonu bazowego (co host page rozszerza) w
ustawieniach: `LIVE_OPERATIONS = {"BASE_TEMPLATE": "base.html"}` (§15).

### 4.5 Anulowanie

- Strona operacji ma przycisk „Anuluj" (POST → `cancel` view) ustawiający
  `cancel_requested=True` na operacji.
- W `run()` deweloper sprawdza `p.check_cancelled()` w pętli (np. w
  `p.track`, który robi to automatycznie co iterację) — rzuca
  `OperationCancelled`, framework łapie, oznacza operację jako anulowaną i
  renderuje fragment „anulowano" w `#op-result`.
- Anulowanie jest kooperacyjne (nie zabija wątku/zadania siłą) — proste,
  przenośne między backendami zadań (§15).

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

> **UWAGA (po review, B2/B3):** htmx-ext-ws **nie jest** dziś w projekcie
> (jest tylko core htmx 1.9.12, `package.json`). Wybór klienta (htmx-ext-ws
> vs własny mikro-klient) to otwarta **decyzja** — patrz §13/§17. Poniższy
> opis protokołu jest niezależny od wyboru klienta (oba realizują OOB-swap
> po `id` z wiadomości WS). Każdy `p.*` z workera (sync) wysyła przez
> `async_to_sync(channel_layer.group_send)(...)`.

- Transport: **Django Channels** (ASGI) + klient OOB-swap (§13/§17).
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

> **Log — dedupe przez numer sekwencyjny (§17, W1).** `beforeend` NIE jest
> idempotentny, więc nie wystarczy „pełny log na reconnect". Każda linia ma
> `nr` (rosnący). Live-append niesie `nr`; klient stosuje linię tylko gdy
> `nr > last_seen` (atrybut `data-nr` + drobny hook). Connect wysyła **pełny
> log** (`innerHTML`) i ustawia `last_seen` = `log_seq`. To eliminuje zarówno
> duplikację (powtórki ignorowane), jak i lukę (snapshot ma wszystko do
> `log_seq`). Kolejność w consumerze: **najpierw snapshot, potem dołączenie
> do grupy** — z dedupe po `nr` okno wyścigu jest nieszkodliwe.

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
    cancel_requested = BooleanField(default=False)    # kooperacyjne anulowanie
    cancelled = BooleanField(default=False)
    traceback = TextField(null=True, blank=True)

    # Stan do projekcji/resync:
    status_text = CharField(max_length=255, blank=True, default="")
    percent = PositiveSmallIntegerField(default=0)
    log = JSONField(default=list)          # lista {nr, text} — nr do dedupe (§17, W1)
    log_seq = PositiveIntegerField(default=0)         # ostatni numer linii logu
    result_context = JSONField(null=True, blank=True) # KONTEKST wyniku (nie HTML!) §17 W2

    class Meta:
        abstract = True
        ordering = ["-created_on"]

    # do nadpisania przez dewelopera:
    def run(self, p): raise NotImplementedError

    # framework (auto-derivacja §4.4) — deweloper zwykle nie rusza:
    #   host_template_name  -> "<app>/<snake(klasa)>.html"
    #   result_template_name-> "<app>/<snake(klasa)>_result.html"
    #   channel_name        -> f"liveop.{pk}" (ukryte przed deweloperem)
    # task_run() NIE opakowuje run() w jedną transakcję (§17, B1): stan live
    # (status/percent/log/stage) commituje się NATYCHMIAST i niezależnie od
    # mutacji domenowych; p.* robi group_send od razu (nie on_commit).
```

- **Stan live jest trwały i zacommitowany na bieżąco** → snapshot na reconnect
  widzi rzeczywistość (klucz: §17/B1).
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

## 13. Decyzje

**Rozstrzygnięte (po przeglądzie):**
- **Dystrybucja**: standalone, reusable **`django-live-operations`** (importowane
  jako `live_operations`), zdekuplowane od BPP — patrz §15.
- **Nazwy szablonów**: **auto-derivacja** z klasy operacji (§4.4); brak ręcznych
  nazw w `p.result()` / fragmentach.
- **Backend zadań**: **agnostyczny** (nie wiążemy się z Celery) — pluggable
  runner (Celery / wątek / sync), patrz §15.
- **Wynik jako osobny URL**: tak — host page pod GET renderuje od razu wynik dla
  zakończonej operacji (deep-link/powrót), §9.

**Do rozstrzygnięcia przed planem:**
0. **[KLUCZOWE] Klient transportu (B2/B3)**: htmx-ext-ws (dociągnąć 1-plikowe
   rozszerzenie do htmx 1.9.12 + **spike** na teardown/redial socketu przy
   `chain_to`) **vs** własny mikro-klient (pełna kontrola, ale trzeba
   zaimplementować OOB-swap + cykl życia socketu i to przetestować).
   **Rekomendacja: htmx-ext-ws** — mniejsze ryzyko, htmx już jest; mikro-klient
   tylko jeśli spike pokaże, że ext nie obsługuje teardown-on-swap. Patrz §17.
1. **Reużycie `channels_broadcast`**: reużyć **tylko auth/token/subscription**
   (`security.py`), a **transport przepisać** na HTML-fragment/OOB (jego model
   JSON-dict to dokładnie ta krucha ścieżka, którą zabijamy). NIE dziedziczyć
   po `NotificationsConsumer`. (§17)
2. **Log storage**: `JSONField` (proste) vs osobny model wierszy (skalowalne,
   filtrowalne). Rekomendacja: `JSONField` w v1, model wierszy jako opcja.
3. **htmx `ws` ext**: pakiet shipuje własny mały bund?owany klient (vanilla WS +
   OOB-swap, bez zależności od kompilacji htmx-ext), czy wymaga htmx-ext-ws od
   konsumenta? Rekomendacja: shipować samodzielny mikro-klient (zero zależności
   build-time u konsumenta).
4. **Pull-fallback** w v1: tak/nie (produkcja BPP ma ASGI/Daphne; pakiet i tak
   powinien działać bez ASGI w trybie degradacji — rekomendacja: tak, opcjonalny).
5. **Lokalizacja w monorepo**: katalog `django-live-operations/` w korzeniu repo
   (własny `pyproject.toml`, dep editable z BPP) — patrz §15.

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

---

## 15. Pakiet `django-live-operations` (standalone, reusable)

To **osobny, samodzielny pakiet** — nie część domeny BPP. BPP jest tylko jego
pierwszym konsumentem.

**Layout (katalog w korzeniu monorepo, własny `pyproject.toml`):**
```
django-live-operations/
  pyproject.toml            # name = "django-live-operations"; import: live_operations
  README.md
  live_operations/
    __init__.py
    apps.py                 # AppConfig
    models.py               # LiveOperation (abstract), miksiny stanu
    progress.py             # Progress + p.stage(), OperationCancelled
    naming.py               # class_to_snake, resolvery szablonów/kanału
    runner.py               # backend-agnostyczny enqueue (Celery/thread/sync)
    consumers.py            # LiveOperationConsumer (Channels)
    routing.py              # websocket_urlpatterns
    security.py             # token subskrypcji, autoryzacja właściciela
    views.py                # Create/Live/List/Cancel/Restart (CBV miksiny)
    urls.py
    templatetags/live_operations.py   # {% live_operation op %}
    conf.py                 # settings dict LIVE_OPERATIONS + defaults
    templates/live_operations/
      operation.html        # domyślny host page (fallback)
      _regions.html _status.html _progress.html _log.html
      _result.html _stages.html _cancelled.html
    static/live_operations/
      live-operations.js    # mikro-klient WS+OOB (zero zależności build-time)
  tests/                    # pytest + pytest-django + channels communicator
  example/                  # demo project (upload→analiza→wyniki, 5 etapów)
```

**Zasady pakietu:**
- **Zero zależności od BPP.** Importy tylko: Django, `channels`. Żadnego
  `from bpp...`. (To warunek reusability i późniejszego wydania na PyPI.)
- **Backend zadań agnostyczny.** `runner.py` definiuje interfejs
  `enqueue(operation)`; dostarczone adaptery: `celery`, `threading`
  (dev/test), `eager`/`sync`. Konsument wybiera w ustawieniach. Pakiet
  **nie** zależy od Celery (Celery to opcjonalny extra).
- **Mikro-klient zamiast zależności front-end.** `live-operations.js` (kilka
  KB, vanilla): otwiera WS, na wiadomość = HTML, robi OOB-swap po `id`
  (`hx-swap-oob`-kompatybilnie); wskaźnik połączenia; auto-reconnect. Nie
  wymaga od konsumenta kompilacji htmx-ext. (Współpracuje z htmx, ale go nie
  wymaga.)
- **Ustawienia** (`conf.py`):
  ```python
  LIVE_OPERATIONS = {
      "BASE_TEMPLATE": "base.html",     # co rozszerza host page
      "RUNNER": "celery",               # celery|threading|eager
      "THROTTLE_HZ": 10,                # max wysyłek/s dla percent/track
      "PULL_FALLBACK": False,           # degradacja bez ASGI (§7.4)
  }
  ```
- **Publiczne API** (stabilne): `LiveOperation`, `Progress`, `OperationCancelled`,
  miksiny widoków, `{% live_operation %}`. Reszta — wewnętrzne.
- **Wpięcie do BPP**: dependency editable (`uv add --editable
  ./django-live-operations`) + `live_operations` w `INSTALLED_APPS` +
  `routing` w ASGI; potem pilotaż `import_punktacji_zrodel`.
- **CI/jakość** (docelowo, jak inne pakiety iplweb): macierz Python×Django,
  `pytest-testcontainers-django` dla Postgresa/kanału, ruff, pre-commit.

---

## 16. Etapy (stages) i łańcuchowanie — wszystko bez reloadu

To bezpośrednio modeluje „normalną" live-operację: **wrzuć plik → analiza →
wyniki**, gdzie „analiza" sama może mieć N pod-etapów.

### 16.1 Etapy wewnątrz JEDNEJ operacji (zalecane dla „N faz analizy")

Operacja deklaruje etapy; `p.stage(...)` to context manager, który rysuje
**stepper** (`#op-stages`) i skopuje postęp/log do bieżącego etapu:

```python
class ImportPunktacji(LiveOperation):
    stages = ["Wczytanie", "Walidacja", "Dopasowanie", "Zapis", "Raport"]

    def run(self, p):
        with p.stage("Wczytanie"):
            dane = wczytaj_plik_jcr(self.plik.path)

        with p.stage("Walidacja"):
            for cz in p.track(dane.czasopisma, label="Sprawdzam"):
                waliduj(cz)

        with p.stage("Dopasowanie"):
            for cz in p.track(dane.czasopisma, label="Dopasowuję"):
                p.log(f"{cz.nazwa}: {dopasuj(cz)}")

        with p.stage("Zapis"):
            zapisz(dane, self)

        with p.stage("Raport"):
            p.result(podsumowanie=policz(dane))     # finał in-place
```

Zachowanie:
- **`#op-stages`** renderuje stepper (np. 5 kropek/kroków): zrobione ✓,
  bieżący ●, przyszłe ○. Wejście w `stage` → oznacz aktywny + render; wyjście
  bez wyjątku → ✓; wyjątek → ✗ i `p.error`.
- Pasek `#op-progress` i log dotyczą **bieżącego etapu** (reset paska na
  wejściu w etap). Opcjonalny pasek „ogólny" = `(zrobione_etapy + ułamek)/N`.
- Stan etapów jest częścią snapshotu (§7.3) → reconnect pokazuje właściwy
  etap. Stepper-swap jest idempotentny.
- **Bez reloadu** — to nadal jedna strona, jeden socket, jedna operacja.
  Etapy to po prostu strukturyzowane sekcje wewnątrz `run()`.

To pokrywa „mieć np. 5 etapów long-running jak analiza pliku" **bez** mnożenia
obiektów/kanałów/stron.

### 16.2 Łańcuchowanie ODDZIELNYCH operacji (gdy etapy to osobne byty)

Gdy fazy są naprawdę odrębnymi operacjami (inny model, inne wejście, osobno
wznawialne, inny `run()`), łączymy je w łańcuch — **też bez reloadu**:

```python
def run(self, p):
    ...
    # zamiast p.result(): przekaż sterowanie kolejnej operacji
    nast = AnalizaPliku.objects.create(owner=self.owner, plik=self.plik)
    p.chain_to(nast)          # finalizuje bieżącą i montuje następną in-place
```

Mechanika (kluczowe, że bez nawigacji):
- `p.chain_to(next_op)` finalizuje bieżącą operację i wysyła OOB-swap
  **całego kontenera** `#op-root`, w którym nowy element ma świeży
  `ws-connect` do kanału `next_op`:
  ```html
  <div id="op-root" hx-swap-oob="true"
       data-ws="{% url 'live_operations:ws' next_op.pk %}">
    {# regiony next_op + auto-start #}
  </div>
  ```
  Mikro-klient (lub htmx-ws) na podmianę elementu z `data-ws`/`ws-connect`
  **zamyka stary socket i otwiera nowy** do `next_op`. Strona się nie
  przeładowuje — zmienia się tylko zawartość kontenera i adres socketu.
- `next_op` startuje (enqueue) i od tej chwili działa jak każda operacja:
  snapshot na connect, postęp, wynik.
- Łańcuch może być dłuższy (A→B→C); każdy człon to samodzielna, wznawialna
  operacja z własnym deep-linkiem.

### 16.3 Którego użyć?

| Sytuacja | Wybór |
|---|---|
| „upload → analiza (kilka faz) → wyniki", jeden spójny przebieg | **Etapy** (§16.1) — jedna operacja, prościej |
| Fazy = odrębne, wznawialne byty (różne modele/wejścia, osobne uprawnienia, możliwy restart pojedynczej fazy) | **Łańcuch** (§16.2) |
| Faza opcjonalna/warunkowa, rozgałęzienia | Łańcuch (`p.chain_to` zależny od wyniku) |

### 16.4 Wpływ na model i regiony

- Model: `stages = []` (deklaracja, opcjonalna), `current_stage` (int),
  `stage_states` (JSON: per-etap status). Wszystko częścią snapshotu.
- Nowy region `#op-stages` + fragment `_stages.html` (stepper).
- `p.chain_to` korzysta z istniejącego mechanizmu OOB-swap — żadnej nowej
  infrastruktury transportowej; to wciąż „projekcja stanu po WS".

---

## 17. Rozstrzygnięcia po adversarial review (twarde wymagania implementacji)

Te punkty są **wiążące** dla planu — bez nich „snapshot = źródło prawdy" jest
nieprawdziwe pod modelem workera z jedną transakcją.

### 17.1 (B1) Dwie ścieżki stanu — live commituje się natychmiast
- `task_run()` **NIE** opakowuje całego `run()` w jedną transakcję.
- **Stan live** (`status_text`, `percent`, `log`/`log_seq`, `current_stage`,
  `stage_states`, na końcu `result_context` + `finished_*`) zapisywany jest
  **natychmiastowym, niezależnym commit-em** (autocommit / osobny, krótki
  `atomic` per-zapis, lub dedykowane połączenie). Dzięki temu snapshot
  konsumenta (osobne połączenie ASGI, READ COMMITTED) **widzi** bieżący stan.
- **Mutacje domenowe** w `run()` (np. zapisy `Punktacja_Zrodla`) zarządzają
  własną atomicznością — deweloper opakowuje je `transaction.atomic()` tam,
  gdzie tego chce. Ich rollback **nie** cofa już-pokazanego postępu (to
  akceptowalne; postęp to log przebiegu, nie dane domenowe).
- `p.*` wysyła `group_send` **od razu** (nie `transaction.on_commit`), bo
  ścieżka live jest już zacommitowana → stream i snapshot są spójne.

### 17.2 (W5) Throttling obejmuje TAKŻE zapis do DB
- `p.percent`/`p.track` koalescjonują **i wysyłkę WS, i commit stanu**:
  domyślnie ≤ ~10 Hz **oraz** ≥1% zmiany. 100k iteracji → rząd setek
  commitów/sekund, nie 100k UPDATE-ów. Akceptujemy sub-sekundowe opóźnienie
  snapshotu. `p.log` może mieć osobny, wyższy budżet (linie są tanie), ale i
  tak batch'owany.

### 17.3 (W1) Log: numer sekwencyjny + dedupe klienta
Jak w §7.3: linie mają `nr`; klient stosuje tylko `nr > last_seen`; connect
wysyła pełny log + `log_seq`. Snapshot-przed-dołączeniem-do-grupy + dedupe.

### 17.4 (W2) Wynik: przechowujemy KONTEKST, renderujemy na żądanie
- Model trzyma `result_context` (JSON), **nie** `result_html`. Deep-link GET
  zakończonej operacji renderuje aktualny szablon z zapisanego kontekstu →
  poprawki szablonu/CSS działają wstecz, brak puchnięcia DB.
- Kontrakt: deweloper utrzymuje szablon wyniku kompatybilny wstecz z
  kontekstem (zwykle `{object, operation, **extra}`).

### 17.5 (W3) „Runner-agnostic" — co naprawdę znaczy live
- **Live wymaga**: runner **out-of-process** (Celery worker) **+ Redis
  channel layer** (jest: `settings/base.py` `RedisChannelLayer`).
- **`eager`/`sync`**: `run()` wykonuje się przed połączeniem socketu →
  `group_send` trafia w pustą grupę → użytkownik widzi **tylko finalny
  snapshot**. To tryb test/degradacja, **nie** „live". Udokumentować wprost.
- **`threading` + `InMemoryChannelLayer`**: dostawa cross-loop jest zawodna
  (layer związany z pętlą) → do live i tak potrzebny Redis. InMemory tylko do
  izolowanych testów consumera.

### 17.6 (W4) Test plan — trzy poziomy, świadomie
- **Consumer (unit)**: `WebsocketCommunicator`, ręczny `group_send` →
  asercja fragmentu; connect→snapshot; reconnect→idempotencja.
- **`Progress` (unit)**: wstrzyknięty **fake channel layer** (przechwytuje
  `group_send`) → asercja, że `p.*` woła `async_to_sync(group_send)` z
  poprawnym fragmentem; throttling; numeracja logu; stepper.
- **Round-trip (integration)**: worker→layer→consumer **na Redisie**
  (`pytest-testcontainers-django`), nie InMemory/eager.

### 17.7 (async/sync) Granica
Każdy send z sync-workera: `async_to_sync(channel_layer.group_send)(grupa,
{...})`. Subskrypcja/odsubskrypcja w consumerze: `async_to_sync(group_add/
group_discard)`. (Wzorzec jak w `channels_broadcast.consumers`.)

### 17.8 (naming) `class_to_snake` — algorytm i ucieczka
- Algorytm: granice wstaw przed wielką literą poprzedzoną małą/cyfrą oraz
  w sekwencjach akronimów (`ImportPBN2` → `import_pbn2`, nie `import_p_b_n2`)
  — użyć sprawdzonej reguły (np. dwa podstawienia regex jak w `inflection`).
- **Ucieczka**: `host_template_name` / `result_template_name` na klasie albo
  `template=` w `p.result/p.swap`. Auto-derivacja to domyślny komfort, nie
  klatka.

### 17.9 Status wpływu na resztę speca
- §10: `result_html` → `result_context`; pole `log_seq`; brak „jednej
  transakcji".
- §6: wybór klienta = decyzja §13.0; `async_to_sync` jawne.
- §7.2/§7.3: spójność snapshotu zależy od 17.1 (immediate-commit lane).
- §15: runner: `celery+redis` = live; `eager` = snapshot-only (test).
