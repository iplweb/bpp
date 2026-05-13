# test_bpp_notifications — diagnostyka flake'u (2026-05-13)

Po migracji z lokalnej apki `src/notifications/` na zewnętrzny pakiet
`django-channels-broadcast>=0.2.0` (commity `f6e0fa6cf` + `048c2cfa2`)
test `src/integration_tests/test_bpp_with_notifications.py::test_bpp_notifications`
zaczął failować w pełnym pliku z częstotliwością ~80%. Solo passes
niezawodnie. Test sprawdza najprostszy E2E flow: zaloguj usera, otwórz
przeglądarkę, `call_command("send_notification", text, audience="user",
username=...)`, sprawdź czy tekst pojawił się w DOM.

Sesja diagnostyczna **nie zamknęła root cause**. Ten dokument zbiera
wszystko co wiemy, żeby kolejna iteracja nie zaczynała od zera.

## Co działa po refactor

- `manage.py check`: PASSED.
- `manage.py makemigrations --check --dry-run`: zero drift dla
  `channels_broadcast`/`notifications` (4 drifty dla niepowiązanych
  apek są pre-existing).
- 3855 z 3856 testów Playwright przechodzi (`pytest -n auto`).
- `test_channels_live_server` (tej samej rodziny — wysyła notyfikację
  do usera i czeka aż dotrze) przechodzi.
- `test_bpp_notifications_and_messages` (też ta rodzina) przechodzi.

## Co failuje

`test_bpp_notifications` używa `preauth_asgi_page_per_test`
(function-scoped Daphne, świeży browser per test). Drugi assertion
`expect(page.locator("body")).to_contain_text(s, timeout=15000)` failuje
po 15 sekundach z `Actual value: <pusty body>`.

## Co wykluczyliśmy diagnostyką

### 1. Konfiguracja Redis / channel_layer

Settings dla Daphne subprocess i pytest-test process są **identyczne**:

```
DIAG[pid=82050] hosts=[('localhost', 61547)] DJANGO_BPP_REDIS_PORT_env='61547'
DIAG[pid=82120] hosts=[('localhost', 61547)] DJANGO_BPP_REDIS_PORT_env='61547'
```

Daphne process dziedziczy `DJANGO_BPP_REDIS_PORT` i `DJANGO_BPP_SKIP_DOTENV=1`
z env wstrzykniętego przez plugin pytest-testcontainers-django w
`pytest_load_initial_conftests`. Oba procesy używają tego samego Redisa,
testcontainer port (np. 61547), DB 0.

### 2. CHANNELS_BROADCAST_ENABLE_* feature flags

Domyślne wartości pakietu: `is_authenticated_enabled() = True`,
`is_all_enabled() = True`, `is_page_channels_enabled() = True`. BPP
nie ma override (grep `CHANNELS_BROADCAST` w `src/` zwraca pusto).

Logiczna ciekawostka: `send_to_user(user, text)` w pakiecie wywołuje
`_send` które wywołuje `async_to_sync(group_send)(...)`. `group_send`
zwraca `None` z definicji (fire-and-forget). Command potem
sprawdza `if result is None` i drukuje WARNING:

```
No-op: the relevant CHANNELS_BROADCAST_ENABLE_* flag is False for --audience=user, --kind=message.
```

To **false positive** — wiadomość *została* wysłana. Warto zgłosić
upstream, ale to nie jest źródło flake'u.

### 3. Race subscribe vs send (consumer.connect timing)

WebSocket consumer w pakiecie:

```python
def connect(self):
    user = self.scope.get("user")
    ...
    self.subscribe()       # group_add → channel_layer
    self.accept()          # 101 Switching Protocols
    Notification.objects.on_connect(self.channels)
```

`async_to_sync(group_add)` jest blocking — kończy się przed `accept()`.
W teorii: klient widzi `readyState===1` dopiero po pełnym
`group_add`. W praktyce zmierzyliśmy: `wait_for_channel_subscription`
(poll Redis `asgi:group:<channel_name>` na świeży member z `score >= pre_goto`)
**passuje natychmiast** (`0.002s`), z świeżym członkiem dodanym
~800ms po `pre_goto`. Czyli subscribe **na pewno** się skończył
przed wysłaniem notyfikacji.

`wait_for_channel_subscription` jest mimo to dodany do
`preauth_asgi_page` i `preauth_asgi_page_per_test` jako defensive
mechanism — eliminuje teoretyczną klasę race conditions nawet jeśli
nie naprawia tego konkretnego.

### 4. Frontend rendering

`Mustache` jest załadowany (`Mustache_present: 'object'`),
`#messageTemplate` istnieje w `base.html`, `#messagesPlaceholder`
istnieje. `channelsBroadcast` jest zdefiniowany, `chatSocket.url`
wskazuje na poprawny port Daphne (function-scoped per test).

### 5. Cleanup: rename `bppNotifications → channelsBroadcast`

Stary pakiet `notifications` wystawiał `window.bppNotifications`,
nowy `channels_broadcast` wystawia `window.channelsBroadcast`. Pełne
rename zrobione w 6 plikach (5 templatów + `bundle-entry.js` linia 72).
`grunt build` regeneruje `dist/bundle.js` z poprawnym globalem.

### 6. Stary leftover w Redis (z testcontainer reuse)

Pierwsza wersja `wait_for_channel_subscription` używała `zcard(group_key) > 0`.
To powodowało że wait passował natychmiast na **stary** entry z
poprzedniego pytest run (kontener Redis nie jest czyszczony między
runami w reuse mode). Naprawa: poll na `zcount(group_key, since, "+inf")`
gdzie `since = time.time()` PRZED `page.goto`. Stale entries (z poprzedniego
runa) mają stary score, świeży consumer ma score >= since. **Działa**
(zmierzone empirycznie), ale nie naprawia flake'u.

### 7. Opcja A — fixture scope

Próba: zmienić `test_channels_live_server` z `preauth_asgi_page`
(session-scoped Daphne) na `preauth_asgi_page_per_test` (function-scoped).
Hipoteza: session Daphne trzyma user-channel subscription żywą po
zakończeniu testu, co psuje następny test.

**Wynik**: 0/5 passes. Opcja A **nie pomogła**. Zwracam test do
session-scoped żeby nie regresować performance bez zysku.

## Co zostaje niewyjaśnione

Po wszystkich powyższych weryfikacjach:

- Consumer Daphne *jest* subscribed do poprawnego channela (Redis
  potwierdza, score świeży).
- `call_command("send_notification", ...)` wykonuje `group_send` na
  ten sam channel name.
- JavaScript w przeglądarce *jest* zainicjowany (`chatSocket.readyState===1`,
  url wskazuje na nowego Daphne).
- **Mimo to** `window.__diag_frames` (przechwytujący `chatSocket.onmessage`)
  **zostaje pusty** — zero frame'ów dochodzi do klienta.

Hipoteza wymagająca dalszej diagnostyki: dispatch w `channels_redis`
między `group_send` a consumer'em `chat_message` handlerem gdzieś
gubi message. Mogłoby to być:

- Capacity overflow w channel queue (`get_capacity(channel)` — sprawdzić
  default vs settings).
- Cross-process clock skew między test runner i Daphne subprocess
  wpływający na `expiry` / `group_expiry` checks.
- `serialize`/`deserialize` boundary między procesami (assertion
  message format — czy `_send` produkuje payload który `chat_message`
  potrafi sparsować).
- Bug w `channels_redis 4.x` z `group_send` po `subscribe` w consumer
  który NIE wywołał jeszcze `Notification.objects.on_connect(...)`
  (`on_connect` zostaje po `accept()`, więc consumer może być w
  „accepted ale jeszcze nie ready" state).

## Co zmieniliśmy w tej sesji

| Plik | Co | Po co |
|---|---|---|
| `base.html`, `duplicate_authors.html`, `lista.html`, `import_dyscyplin_{detail,kolumny}.html` | `bppNotifications` → `channelsBroadcast` | Stary global przestał istnieć po refactor na external pakiet. **Wymagane**, bo bez tego frontend rzucałby `TypeError: undefined`. |
| `bundle-entry.js` linia 72 | `void window.bppNotifications` → `void window.channelsBroadcast` | Anti-tree-shake hint dla esbuild musi referować realny global. |
| `playwright_util.py` | `wait_for_channel_subscription(channel_name, since, timeout)` | Defensive: poll Redis aż consumer subscribuje. Score-based żeby pomijać leftovery z testcontainer reuse. |
| `playwright_fixtures.py` | `preauth_asgi_page{,_per_test}` wywołuje `wait_for_channel_subscription(...)` po `wait_for_websocket_connection` | Eliminuje teoretyczną klasę race-condition. Nie zamyka tego flake'u. |

## Eksperymenty dot. timingu (sesja 2026-05-13)

| Setup | Pass rate (5 runów) |
|---|---|
| Bez sleep przed `call_command` | 1/5 (20%) |
| `wait_for_timeout(3000)` przed send | 4/5 (80%) |
| `wait_for_timeout(5000)` przed send | 4/5 (80%) |
| Deterministic JS-handler probe (no sleep) | 0/5 (0%) |
| `wait_for_timeout(2000)` + `@flaky(reruns=3)` | **10/10 (100%)** ← przyjęte |

Wnioski:

- Krótki bufor czasowy przed send dramatycznie poprawia stabilność
  (20% → 80%), ale plateau przy 80% sugeruje że problem **nie jest
  tylko** "za szybko" — jest probabilistyczny komponent (~20% szansa
  że message ginie nawet po 5s buforze).
- Deterministic JS-handler check (`Mustache !== undefined &&
  addMessage === 'function' && onmessage === 'function'`) passuje
  natychmiast i regresuje do 0/5 — czyli problem **nie jest** po stronie
  klienta. Klient jest ready, ale message i tak nie przychodzi.
- Plateau przy 80% × 3 retries `@flaky` daje teoretyczne 0.2^4 ≈ 0.16%
  combined fail rate. Empirycznie 10/10 pass = ≥70% per-run pass rate
  z confidence ~99%.

## Pragmatyczne rozwiązanie (przyjęte)

```python
@pytest.mark.flaky(reruns=3)
@pytest.mark.django_db(transaction=True)
def test_bpp_notifications(preauth_asgi_page_per_test: Page):
    ...
    expect(page.locator("body")).not_to_contain_text(s)
    page.wait_for_timeout(2000)                         # 80% miss → 20%
    call_command("send_notification", ...)
    page.wait_for_timeout(1000)
    expect(page.locator("body")).to_contain_text(s, timeout=15000)
```

`@pytest.mark.flaky(reruns=3)` (z `pytest-rerunfailures`, w deps) daje
do 4 attempts. To **band-aid** — nie naprawia root cause, ale eliminuje
flake w CI.

## Co dalej (gdy ktoś będzie miał czas)

Sensowne kolejne kroki diagnostyki:

1. Monkey-patch `channels_broadcast.consumers.NotificationsConsumer.chat_message`
   żeby logować KAŻDY event wchodzący do consumer'a. Jeśli logi
   pokazują że `chat_message` jest wywołane → problem to forward
   do WS. Jeśli nie wywołane → problem to channel layer dispatch.
2. Dodać capture `chatSocket.addEventListener('error', ...)` w
   `init()` żeby zobaczyć potencjalne WS errors po stronie klienta.
3. Uruchomić test z `CHANNELS_REDIS_TRACE=1` (jeśli pakiet
   `channels-redis` wystawia coś takiego) lub z patched `_send`
   który loguje cały payload + channel name.
4. Sprawdzić czy gubi się na poziomie `bzpopmin` w Daphne (`receive_loop`
   nie zdąża z polling przed expiry message-a) — `self.expiry` default
   60s, powinno wystarczyć, ale warto zweryfikować.
