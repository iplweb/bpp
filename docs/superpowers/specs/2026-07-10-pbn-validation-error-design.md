# PBNValidationError — czytelny błąd walidacji zamiast szumu w Rollbarze

Data: 2026-07-10
Autor: Michał Pasternak (+ Claude)
Status: zatwierdzony design (wariant A), zrewidowany po DWÓCH turach
adwersaryjnego review (Fable). Runda 1: K1/K2 (bez `__str__`), W1 (bramka
statusu), W2 (`description` w Format 2), W3/D1–D5. Runda 2 (potwierdziła
poprawki r1 + nowe): B1 (parser hostile-input-safe), B2 (retry oświadczeń
re-raise walidacji), A1 (wykluczenie 423, osłabienie „409"), A3 (granica 512
znaków w teście tupli), B3/B4/B7 (uwagi i zakres).

## Problem

Rollbar item [#443](https://app.rollbar.com/a/michal.dtz/fix/item/bpp/443)
(`code_version` `202607.1397rc1`, host `publikacje.up.lublin.pl`):

```
HttpException: (400, '/api/v1/publications',
  '{"code":400,"message":"Bad Request","description":"Validation failed.",
    "details":{
      "openAccess.releaseDate":"Data udostępnienia w otwartym dostępie
        (pełna data albo miesiąc i rok) jest wymagana!",
      "openAccess.releaseDateMonth":"…",
      "openAccess.releaseDateYear":"…"}}')
```

To **odrzucenie danych publikacji przez PBN** (brak daty udostępnienia w
Open Access) — czyli **błąd merytoryczny/danych użytkownika, NIE bug w kodzie
BPP**. Mimo to na synchronicznej ścieżce admina jest traktowany jak nieznany
wyjątek:

- łapany przez generyczny `except Exception` w
  `bpp/admin/helpers/pbn_api/common.py:234`,
- użytkownik dostaje surowy JSON w komunikacie (`Kod błędu: {e}`),
- błąd trafia do Rollbara **dwukrotnie** na jedną nieudaną wysyłkę:
  1. `pbn_client/transport.py:187` `rollbar.report_message` — level `warning`
     (dla 4xx), tytuł „PBN 400 on /api/v1/publications",
  2. `bpp/admin/helpers/pbn_api/common.py:256` `rollbar.report_exc_info` —
     level `error` → **to jest item #443**.

### Czego chce użytkownik

1. **Zero szumu w Rollbarze** dla błędów walidacji PBN (to nie jest błąd kodu
   do zdebugowania — to dane do poprawienia przez redaktora).
2. **Czytelny komunikat** po nieudanej wysyłce zamiast surowego JSON-a.
3. Semantycznie: to jest `ValidationError`, nie `HttpException` — typ wyjątku
   powinien to odzwierciedlać.

## Stan istniejący (co już działa)

**Ścieżka kolejkowa** (`pbn_export_queue`, asynchroniczna) **już** poprawnie
klasyfikuje te błędy:

- `pbn_export_queue/models.py:218` `_is_pbn_validation_error(exc)` rozpoznaje
  dwa formaty odpowiedzi walidacyjnej:
  - **Format 1**: `{"details": {...}}` — dict z niepustym `details`,
  - **Format 2**: `[{"code": "NOT_UNIQUE_PUBLICATION", ...}]` — lista z `code`.
- `pbn_export_queue/models.py:323` — `HttpException` z walidacją →
  `RodzajBledu.MERYTORYCZNY` (błąd usera, do naprawy), bez Rollbara; inny
  `HttpException` → `TECHNICZNY`.
- Migracje `0005_reclassify_old_validation_errors` /
  `0006_reclassify_list_format_validation_errors` — jednorazowe poprawki
  danych historycznych (TECH→MERYT); dotyczą istniejących rekordów, nie
  wpływają na nowe.

**Problem jest wyłącznie na synchronicznej ścieżce admina**
(`sprobuj_wyslac_do_pbn`), która nie ma tej klasyfikacji.

### Klasa `HttpException`

`pbn_client/exceptions.py:29`:

```python
class HttpException(Exception):
    def __init__(self, status_code, url, content):
        self.status_code = status_code
        self.url = url
        self.content = content
        try:
            self.json = json.loads(content[:4096])
        except (json.JSONDecodeError, ValueError, TypeError):
            self.json = None
```

`self.json` to sparsowane body — dla walidacji `json["details"]` jest już
słownikiem `{pole: komunikat}`, a komunikaty są po polsku i czytelne. Trzy
klucze (`releaseDate`, `releaseDateMonth`, `releaseDateYear`) często niosą
**ten sam** tekst → warto deduplikować.

## Rozwiązanie (wariant A): dedykowany `PBNValidationError(HttpException)`

Rozpoznanie „to walidacja" przenosimy do **jednego wąskiego gardła**
(`transport._check_error_response`) i podnosimy dedykowany, samo-opisujący
typ wyjątku będący **podklasą `HttpException`** (pełna wsteczna zgodność).

### Dlaczego podklasa HttpException, a nie Django `ValidationError`

- Każdy istniejący `except HttpException` (m.in. klasyfikacja w
  `pbn_export_queue`, handlery w `common.py`) dalej łapie wyjątek — **zero
  regresji**.
- Django `ValidationError` zrywa łańcuch `except HttpException` i niesie
  bagaż integracji z formularzami, którego tu nie ma (to odrzucenie z API
  zewnętrznego, nie walidacja formularza Django).
- Semantyka „to walidacja" i tak jest wyrażona nazwą typu
  (`PBNValidationError`) oraz interfejsem (`.details`, `.user_messages()`).

### Komponenty

#### 1. `pbn_client/exceptions.py` — nowy typ + helper detekcji

```python
def parse_pbn_validation_details(parsed_json):
    """Zwraca listę komunikatów walidacyjnych PBN lub None, gdy to nie
    jest odpowiedź walidacyjna.

    Rozpoznaje dwa formaty odpowiedzi PBN:
    - Format 1: {"details": {pole: komunikat, ...}} — dict z niepustym details
    - Format 2: [{"code": ..., "description": ...}, ...] — lista z kodami

    Kolejność komunikatów zachowana wg wejścia; deduplikacja zachowuje
    pierwszą kolejność wystąpienia.
    """
```

**KRYTYCZNE — parser MUSI być odporny na obcy input (poprawka po review Fable,
B1).** Body pochodzi z PBN (obcy serwis); wartości mogą NIE być stringami.
Zweryfikowane: PBN potrafi zwracać **listy** w `details` (dowód: renderer
kolejki `pbn_export_queue/templatetags/pbn_queue_extras.py:110-113` już broni
się `", ".join(str(v) for v in val) if isinstance(val, list) else str(val)`).
Naiwny dedup `dict.fromkeys(details.values())` na wartości-liście rzuca
`TypeError: unhashable type: 'list'` — i to **w środku `_check_error_response`,
czyli w trakcie obsługi błędu HTTP** (zastąpiłby realny błąd bezużytecznym
TypeError, także na ścieżce kolejki → `TECHNICZNY` + Rollbar). Wymagania:

- Każda wartość `details` przed dedupem: jeśli `list`/`tuple` →
  `", ".join(str(v) for v in val)`; w przeciwnym razie `str(val)`. Dedup
  dopiero na już-stringach.
- Format 2: guard `isinstance(el, dict)` dla każdego elementu (element
  nie-dict, np. goły string, pomijany — nie `el.get(...)` na nie-dict →
  `AttributeError`).
- `parsed_json` nie-dict/nie-lista, pusty, `None` → `None`.
- Cała funkcja „hostile input safe" — żadne wejście z PBN nie może z niej
  wyrzucić wyjątku (test to utrwala, B8).

- Format 1 → wartości słownika `details` (skoercowane do str jw.),
  zdeduplikowane z zachowaniem kolejności.
- Format 2 → dla każdego elementu-dict łańcuch fallbacków
  **`message` → `description` → `code`** i tylko gdy nic z tego nie ma →
  element pominięty. **Uwaga (zweryfikowane w migracji `0006`):** realny
  Format 2 to `[{"requestPosition":0,"code":"NOT_UNIQUE_PUBLICATION_ISBN_ISMN",
  "description":"Publikacja o identycznym ISBN..."}]` — element **NIE ma**
  klucza `message`, czytelny polski tekst siedzi w `description`. Fallback
  wyłącznie do `code` pokazałby surowy kod → dlatego `description` jest
  przed `code`.
- `None`/pusty/nierozpoznany → `None` (to NIE walidacja).

```python
class PBNValidationError(HttpException):
    """PBN odrzucił dane (Validation failed). Błąd merytoryczny —
    dane do poprawienia przez użytkownika, NIE bug w kodzie."""

    def __init__(self, status_code, url, content):
        super().__init__(status_code, url, content)
        self.messages = parse_pbn_validation_details(self.json) or []

    def user_messages(self):
        """Zdeduplikowana lista czytelnych komunikatów dla użytkownika."""
        return self.messages
```

**KRYTYCZNE — NIE nadpisujemy `__str__`** (poprawka po review Fable, K1/K2).
`str(PBNValidationError)` musi dalej dawać odziedziczoną **tuplę**
`(status, url, content)`. Powód (zweryfikowany uruchomieniowo):

- `SentData.mark_as_failed` zapisuje `str(e)` do `SentData.exception`
  (`pbn_api/client/publication_sync.py:217-224`);
- widoki szczegółów kolejki parsują ten tekst przez
  `parse_pbn_api_error` (`pbn_export_queue/views/utils.py:151-154`), które
  rozpoznaje błąd PBN m.in. gdy `looks_like_tuple`
  (`text.strip().startswith("(") and "," in text`);
- kolejka zapisuje też `traceback.format_exc()` do `komunikat`
  (`pbn_export_queue/models.py:325`), którego ostatnia linia to `str(e)`.

Nadpisanie `__str__` na `"; ".join(messages)` **zerwałoby** parsowanie tupli
w UI kolejki i **usunęłoby surowy JSON + nazwy pól** z rekordu kolejki —
dokładnie dla kategorii błędów, której ten spec dotyczy. Czytelność na
ścieżce admina zapewnia wyłącznie `user_messages()` (metoda, nie `str`).

Uwaga: `parse_pbn_validation_details` staje się **jednym źródłem prawdy**
detekcji. `pbn_export_queue._is_pbn_validation_error` może z niego korzystać
(patrz p. 4), ale to opcjonalne uproszczenie — nie warunek poprawności.

#### 2. `pbn_client/transport.py` — `_check_error_response`

Obecnie (linie 167–198): każdy status ≥400 → `logger.error` +
`rollbar.report_message` + `raise HttpException`.

Zmiana — **przed** blokiem logowania/Rollbara wykryj walidację:

```python
def _check_error_response(self, ret, url):
    if ret.status_code >= 400:
        if ret.status_code == 423 and smart_content(ret.content) == "Locked":
            raise ResourceLockedException(...)

        content = smart_content(ret.content)

        # Błąd walidacji PBN (details / lista z code) to błąd danych
        # użytkownika, NIE problem techniczny — nie raportujemy do Rollbara,
        # podnosimy dedykowany, samo-opisujący typ. Detekcja PO FORMACIE body,
        # ale BRAMKOWANA statusem: tylko 4xx z wyłączeniem 401/403/423.
        #   - 5xx: NIE tłumimy Rollbara — awaria po stronie PBN warta uwagi,
        #     nawet gdyby body przypadkiem miało kształt walidacji (W1).
        #   - 401/403: to problemy autoryzacji, nie walidacji danych;
        #     403 z body bez access-denied spada tu z post() (D3).
        #   - 423: blokada zasobu (ResourceLocked) — obsłużone wyżej dla body
        #     dosłownie "Locked", ale 423 z innym body też NIE jest walidacją.
        #   - Format 1: zwykle 400. Format 2 (NOT_UNIQUE): status niepotwierdzony
        #     w kodzie (migracja 0006 nie zapisuje kodu HTTP) — detekcja po
        #     formacie body i tak obejmuje całe 4xx, więc niezależna od statusu.
        if 400 <= ret.status_code < 500 and ret.status_code not in (401, 403, 423):
            exc = PBNValidationError(ret.status_code, url, content)
            if exc.user_messages():
                logger.info("PBN validation rejected %s: %s", url, exc)
                raise exc

        logger.error("PBN %s on %s: ...", ...)      # bez zmian
        rollbar.report_message(...)                  # bez zmian
        raise HttpException(ret.status_code, url, content)
```

- Walidacja rozpoznana (format body + status 4xx bez 401/403/423) →
  `PBNValidationError`, **bez** `rollbar.report_message` i bez `logger.error`
  (zamiast tego `logger.info` do lokalnych logów).
- 5xx, 401/403/423, oraz 4xx bez rozpoznanego formatu walidacji → ścieżka bez
  zmian (dalej `HttpException` + Rollbar).
- `423 Locked` (dosłowne body) obsłużone jeszcze wcześniej jako
  `ResourceLockedException` — bez zmian.

> Uwaga (D2): `_check_error_response` to chokepoint **POST/DELETE**. `get()`
> (`transport.py:112-113`) rzuca goły `HttpException` z pominięciem tej
> metody — celowo, bo GET nie waliduje danych użytkownika. „Wąskie gardło"
> dotyczy więc ścieżki zapisu, nie odczytu.

#### 3. `bpp/admin/helpers/pbn_api/common.py` — `sprobuj_wyslac_do_pbn`

Dodaj `except PBNValidationError` **przed** generycznym `except Exception`
(kolejność `except` ma znaczenie — podklasa musi być wcześniej):

```python
except PBNValidationError as e:
    komunikaty = "".join(f"<li>{escape(m)}</li>" for m in e.user_messages())
    notificator.warning(
        f'Publikacja "{link_do_obiektu(obj)}" została odrzucona przez PBN '
        f"z powodu błędów walidacji danych: <ul>{komunikaty}</ul>"
        f"Popraw dane rekordu i spróbuj ponownie. "
        f"{open_in_pbn_link}{open_in_pi_link}"
    )
    if raise_exceptions:
        raise e
    return
```

- **Bez** `rollbar.report_exc_info` — to nie jest błąd kodu.
- Komunikaty z `user_messages()` (już zdeduplikowane) jako lista punktowana.
- `escape()` na komunikatach z PBN (obcy input trafia do HTML notyfikatora)
  — z `django.utils.html`.
- Respektuje `raise_exceptions` (spójnie z pozostałymi handlerami).
- Uwaga (D4, pre-existing): `link_do_obiektu` używa `mark_safe(obj)` na tytule
  rekordu (`bpp/admin/helpers/__init__.py`), więc sam tytuł nie jest
  escapowany — to zastane zachowanie, nie ruszamy go; escapujemy tylko
  świeżo dodawany obcy input z PBN (`user_messages()`).

#### 3b. Ścieżka oświadczeń — retry NIE ponawia walidacji (poprawka B2)

`_check_error_response` to chokepoint **wszystkich** POST/DELETE, więc
`PBNValidationError` może wyskoczyć nie tylko z POST publikacji, ale też z
POST/GET/DELETE oświadczeń (`/api/v2/institution-profile/statements`). Te
operacje mają pętle retry łapiące `except Exception`:

- `pbn_api/client/publication_sync.py:_post_statements_with_retry` (linia
  ~368: `for attempt in range(max_tries): ... except Exception as e:`),
- analogiczne pętle GET/DELETE oświadczeń (`_get_pbn_statements_with_retry`,
  `_delete_statements_selective` i pokrewne).

Bez zmian: walidacyjny 4xx byłby **3× bezsensownie ponawiany** (walidacja się
nie naprawi przez retry), a po wyczerpaniu prób
`_report_statements_failure_and_raise` i tak zaraportowałby do Rollbara +
podniósł `StatementsResendFailedException` → w kolejce `RETRY_LATER` →
pętla. To łamie cel #1 („zero szumu w Rollbarze") i #3.

**Zmiana:** w każdej pętli retry oświadczeń dodać `except PBNValidationError:
raise` **przed** generycznym `except Exception` — walidacja przerywa retry
natychmiast i propaguje w górę. Wtedy:

- na ścieżce admina → nowy handler `except PBNValidationError` w `common.py`
  (czytelny komunikat, bez Rollbara),
- na ścieżce kolejki → `isinstance(exc, HttpException)` + walidacja →
  `MERYTORYCZNY` (poprawnie, zamiast wiecznego `RETRY_LATER`).

Uwaga: POST **samej publikacji** (`upload_publication`) nie ma już pętli
retry na walidacji (`max_retries_on_validation_error` jest DEPRECATED) — tam
`PBNValidationError` i tak propaguje natychmiast. Zmiana dotyczy wyłącznie
pętli oświadczeń.

#### 4. `pbn_export_queue/models.py` — bez zmian funkcjonalnych

`PBNValidationError` jest podklasą `HttpException` z niepustym `.json`
zawierającym `details`, więc:

- `_handle_pbn_exception` → gałąź `isinstance(exc, HttpException)` →
  `_is_pbn_validation_error(exc)` = `True` → `RodzajBledu.MERYTORYCZNY`.

Czyli **klasyfikacja** (MERYT/TECH) działa bez zmian — `_is_pbn_validation_error`
patrzy na `exc.json`, nie na nazwę klasy.

**Prezentacja w UI kolejki** (poprawka po review Fable, W3): działa dzięki
zachowaniu tuplowego `str()` (patrz KRYTYCZNE w p.1). Widoki szczegółów
kolejki (`views/utils.py:parse_pbn_api_error`) rozpoznają błąd PBN przez
`looks_like_tuple` — a tupla zostaje. **Znane ograniczenie pre-existing (NIE
regresja tej zmiany):** matchery po nazwie klasy szukają dosłownie
`"pbn_api.exceptions"` (`pbn_queue_extras.py:_extract_exception_line`,
`views/utils.py:has_pbn_prefix`), a po splicie modułów klasy żyją w
`pbn_client.exceptions`, więc ta gałąź matchowania jest martwa już teraz dla
wszystkich `HttpException`. Nasza zmiana **nie pogarsza** tego (opieramy się
na `looks_like_tuple`, nie na nazwie klasy).

**Opcjonalne hardening (poza rdzeniem, tanie — do decyzji na etapie planu):**
1. Przepięcie `_is_pbn_validation_error` na wspólny
   `parse_pbn_validation_details` (usunięcie duplikacji detekcji; musi
   zachować Format 1 + Format 2).
2. Rozszerzenie matcherów prezentacji o `"pbn_client.exceptions"` i
   `PBNValidationError`, co odblokuje ładne formatowanie per-pole dla nowych
   rekordów (przy okazji naprawia pre-existing W3). Jeśli robione — z testem.

## Testy (TDD)

**Uwaga (D1):** katalog `src/pbn_client/tests/` **nie istnieje** — trzeba go
założyć wraz z `__init__.py`. Nowy plik
`src/pbn_client/tests/test_pbn_validation_error.py`:

1. **transport — walidacja Format 1**: `mock` odpowiedzi 400 z `details` →
   `_check_error_response` podnosi `PBNValidationError`; `rollbar.report_message`
   **nie** został wywołany.
2. **transport — walidacja Format 2 (409, `description`)**: 409 z listą
   `[{"code":"NOT_UNIQUE_PUBLICATION_ISBN_ISMN","description":"..."}]` →
   `PBNValidationError`; `user_messages()` zawiera **`description`**, nie kod
   (W2); brak `report_message`.
3. **transport — 400 bez details**: `PBNValidationError.user_messages()` puste
   → podnosi zwykły `HttpException` + `report_message` wywołany (bez zmian).
4. **transport — 500 z kształtem walidacji**: nawet gdy body 500 ma `details`,
   podnosi `HttpException` + `report_message` level `error`; **NIE**
   `PBNValidationError` (W1 — nie tłumimy 5xx).
5. **transport — 401/403**: nie są traktowane jako walidacja (D3) — ścieżka
   bez zmian.
6. **`parse_pbn_validation_details`**: deduplikacja trzech kluczy o tym samym
   komunikacie → jeden element; kolejność zachowana; Format 2 fallback
   `message`→`description`→`code`; `None` dla nie-walidacji.
7. **`str(PBNValidationError)` = tupla** (K1 guard): dla realistycznego body
   #443 (~476 znaków) `str(exc)` zaczyna się od `(` i zawiera surowy JSON →
   `parse_pbn_api_error(str(exc))` w kolejce daje `is_pbn_api_error=True`
   (`looks_like_tuple`). **Utrwal też granicę (A3):** `parse_pbn_api_error`
   ma guard `len(message_part) > 512 → is_pbn_api_error=False`; test z body
   >512 znaków dokumentuje, że rozpoznanie działa tylko dla krótkich body
   (pre-existing, dotyczy też zwykłego HttpException — nie regresja).
8. **parser hostile input (B1)**: `details` z wartością listą
   (`{"x": ["a","b"]}`) → komunikat `"a, b"`, **bez** `TypeError`; wartość
   `dict`/`None` → skoercowana do str, bez wyjątku; Format 2 z elementem
   nie-dict (`["goły string"]`) → element pominięty, bez `AttributeError`;
   `parsed_json` = str/int/None → `None`.
9. **common — `PBNValidationError`**: fixture `notificator` (spy) →
   `sprobuj_wyslac_do_pbn` woła `notificator.warning` z czytelną listą,
   `rollbar.report_exc_info` **nie** wywołany; przy `raise_exceptions=True`
   wyjątek re-raise’owany. **Escaping (B8):** komunikat z `<script>` w
   `details` renderowany jako encje HTML (assert na `&lt;script&gt;`).
10. **statements retry (B2)**: `PBNValidationError` w
    `_post_statements_with_retry` → **natychmiastowy** re-raise (brak
    ponawiania: `post_discipline_statements` wołany dokładnie raz),
    propaguje w górę.
11. **transport — body >4096 (Ryzyko)**: odpowiedź walidacyjna, której JSON
    po obcięciu `content[:4096]` się nie parsuje → `self.json=None` →
    `user_messages()` puste → fallback do `HttpException` + `report_message`
    (świadoma degradacja do starego zachowania, nie crash).
12. **queue — regresja**: `PBNValidationError` → `_handle_pbn_exception`
    klasyfikuje jako `MERYTORYCZNY` (potwierdzenie braku regresji).

Testy DB: `@pytest.mark.django_db` + `model_bakery.baker.make` gdzie trzeba
rekordu. Detekcja i transport — czyste testy jednostkowe z mockami
(`requests.Response` mock, `rollbar` przez `mocker.patch`).

## Zakres / poza zakresem

W zakresie:
- Nowy typ `PBNValidationError` + helper detekcji (hostile-input-safe, B1).
- Wpięcie w transport (chokepoint POST/DELETE) i w synchroniczną ścieżkę
  admina (`common.py`).
- Re-raise walidacji w pętlach retry oświadczeń (B2).
- Testy jw.

Poza zakresem (YAGNI):
- Refaktor całej hierarchii wyjątków PBN.
- Zmiana klasyfikacji na ścieżce kolejkowej (działa; ewentualnie tylko
  opcjonalne DRY z p. 4).
- Mapowanie nazw pól PBN → etykiety UI (komunikaty PBN są już czytelne).
- **Dedup gubi nazwy pól (B7)**: dla `details` typu `{"isbn":"Pole wymagane!",
  "doi":"Pole wymagane!"}` dedup daje jeden wpis bez wskazania pól.
  Akceptowalne — komunikaty PBN są zwykle samoopisujące (jak w #443);
  doklejanie nazw pól poza zakresem.
- **Ścieżka integratora CLI (B3)**: `pbn_integrator/utils/synchronization.py`
  `_handle_no_pbn_uid` łapie `Exception` z `upload_publication` i **zawsze**
  woła `rollbar.report_exc_info`. Walidacyjne odrzucenia z masowej
  synchronizacji CLI dalej trafią do Rollbara (jako exc_info). Świadome
  ograniczenie — poza celem #443 (ścieżka admina); ewentualny `except
  PBNValidationError` tam to osobna, opcjonalna zmiana.
- Zmiany w migracjach reklasyfikujących (dane historyczne).

## Ryzyka

- **Kolejność `except`**: `PBNValidationError` musi być łapany PRZED
  `HttpException`/`Exception` wszędzie tam, gdzie ma mieć własne zachowanie.
  W `common.py` dokładamy handler przed generycznym `except Exception`. Inne
  miejsca (`except HttpException`) celowo łapią też podklasę — to pożądane
  (wsteczna zgodność).
- **400 nie-walidacyjne**: gdyby PBN zwrócił 400 bez `details` i bez listy z
  `code`, `user_messages()` jest puste → spadamy do zwykłego `HttpException`
  + Rollbar (świadome zachowanie — nieznane 400 warte uwagi).
- **Zachowanie `str()` (K1/K2)**: opieramy się na tym, że `str(exc)` dalej daje
  tuplę (`self.args`). Gdyby ktoś w przyszłości dodał `__str__` lub zmienił
  `HttpException.__init__`, zerwie parsowanie kolejki — dlatego test 7 to
  utrwala jako kontrakt.
- **Pre-existing, żywy bug poza zakresem (D5/B4)**: `raise
  BrakIDPracyPoStroniePBN(e)` (`pbn_integrator/utils/publications.py:361`)
  podaje **jeden** argument do `HttpException.__init__(status_code, url,
  content)` → zweryfikowane uruchomieniowo: `TypeError: __init__() missing 2
  required positional arguments`. Czyli każde 422 „was not exists" w
  `_pobierz_pojedyncza_prace` kończy się `TypeError` zamiast zamierzonego
  wyjątku — to **rozbity kod**, nie tylko kruchy kontrakt. Nie dotyczy tej
  zmiany (inna ścieżka, GET), tylko odnotowane do osobnej naprawy.
- **`smart_content` / obcięcie body**: `HttpException.json` parsuje tylko
  `content[:4096]`. Dla bardzo długich odpowiedzi walidacyjnych część
  komunikatów mogłaby zniknąć — akceptowalne (dotychczasowe zachowanie,
  nie pogarszamy).

## Środowisko pracy

Zgodnie z instrukcją: worktree obok repo
(`~/Programowanie/bpp-pbn-validation-error`), nowy branch od `dev`, baza DEV.
```
