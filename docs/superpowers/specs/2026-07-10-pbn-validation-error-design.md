# PBNValidationError — czytelny błąd walidacji zamiast szumu w Rollbarze

Data: 2026-07-10
Autor: Michał Pasternak (+ Claude)
Status: zatwierdzony design (wariant A)

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
    - Format 2: [{"code": ..., "message": ...}, ...] — lista z kodami błędów

    Kolejność komunikatów zachowana wg wejścia; deduplikacja zachowuje
    pierwszą kolejność wystąpienia.
    """
```

- Format 1 → wartości słownika `details` (komunikaty), zdeduplikowane z
  zachowaniem kolejności.
- Format 2 → `message` (fallback: `code`) każdego elementu listy,
  zdeduplikowane.
- `None`/pusty/nierozpoznany → `None` (to NIE walidacja).

```python
class PBNValidationError(HttpException):
    """PBN odrzucił dane (400 Validation failed). Błąd merytoryczny —
    dane do poprawienia przez użytkownika, NIE bug w kodzie."""

    def __init__(self, status_code, url, content):
        super().__init__(status_code, url, content)
        self.messages = parse_pbn_validation_details(self.json) or []

    def user_messages(self):
        """Zdeduplikowana lista czytelnych komunikatów dla użytkownika."""
        return self.messages

    def __str__(self):
        if self.messages:
            return "; ".join(self.messages)
        return super().__str__()
```

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
        # nie po dokładnym kodzie: Format 1 zwykle 400, Format 2
        # (NOT_UNIQUE_PUBLICATION) bywa 409 — spójnie z queue, które też
        # nie bramkuje po statusie.
        exc = PBNValidationError(ret.status_code, url, content)
        if exc.user_messages():
            logger.info("PBN validation rejected %s: %s", url, exc)
            raise exc

        logger.error("PBN %s on %s: ...", ...)      # bez zmian
        rollbar.report_message(...)                  # bez zmian
        raise HttpException(ret.status_code, url, content)
```

- Walidacja rozpoznana (po formacie body, dowolny ≥400) → `PBNValidationError`,
  **bez** `rollbar.report_message` i bez `logger.error` (zamiast tego
  `logger.info` do lokalnych logów). Spójne z detekcją na ścieżce kolejkowej.
- 4xx/5xx bez rozpoznanego formatu walidacji → ścieżka bez zmian (dalej
  `HttpException` + Rollbar).
- `423 Locked` obsłużone wcześniej (przed detekcją walidacji) — bez zmian.

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

#### 4. `pbn_export_queue/models.py` — bez zmian funkcjonalnych

`PBNValidationError` jest podklasą `HttpException` z niepustym `.json`
zawierającym `details`, więc:

- `_handle_pbn_exception` → gałąź `isinstance(exc, HttpException)` →
  `_is_pbn_validation_error(exc)` = `True` → `RodzajBledu.MERYTORYCZNY`.

Czyli klasyfikacja działa bez zmian. **Opcjonalnie** (nice-to-have, nie
wymagane): przepięcie `_is_pbn_validation_error` na wspólny
`parse_pbn_validation_details`, by usunąć duplikację logiki detekcji. Jeśli
robione — musi zachować dotychczasowe zachowanie (Format 1 + Format 2).

## Testy (TDD)

Nowy plik `pbn_client/tests/test_pbn_validation_error.py` (lub dopięcie do
istniejących testów transportu):

1. **transport — walidacja Format 1**: `mock` odpowiedzi 400 z `details` →
   `_check_error_response` podnosi `PBNValidationError`; `rollbar.report_message`
   **nie** został wywołany.
2. **transport — walidacja Format 2**: 400 z listą `[{"code": ...}]` →
   `PBNValidationError`; brak `report_message`.
3. **transport — 400 bez details**: `PBNValidationError.user_messages()` puste
   → podnosi zwykły `HttpException` + `report_message` wywołany (bez zmian).
4. **transport — 500**: `HttpException` + `report_message` level `error`
   (regresja: nie ruszamy nie-walidacyjnych błędów).
5. **`parse_pbn_validation_details`**: deduplikacja trzech kluczy o tym samym
   komunikacie → jeden element; kolejność zachowana; `None` dla nie-walidacji.
6. **common — `PBNValidationError`**: fixture `notificator` (spy) →
   `sprobuj_wyslac_do_pbn` woła `notificator.warning` z czytelną listą,
   `rollbar.report_exc_info` **nie** wywołany; przy `raise_exceptions=True`
   wyjątek re-raise’owany.
7. **queue — regresja**: `PBNValidationError` → `_handle_pbn_exception`
   klasyfikuje jako `MERYTORYCZNY` (potwierdzenie braku regresji).

Testy DB: `@pytest.mark.django_db` + `model_bakery.baker.make` gdzie trzeba
rekordu. Detekcja i transport — czyste testy jednostkowe z mockami
(`requests.Response` mock, `rollbar` przez `mocker.patch`).

## Zakres / poza zakresem

W zakresie:
- Nowy typ `PBNValidationError` + helper detekcji.
- Wpięcie w transport (chokepoint) i w synchroniczną ścieżkę admina.
- Testy jw.

Poza zakresem (YAGNI):
- Refaktor całej hierarchii wyjątków PBN.
- Zmiana klasyfikacji na ścieżce kolejkowej (działa; ewentualnie tylko
  opcjonalne DRY z p. 4).
- Mapowanie nazw pól PBN → etykiety UI (komunikaty PBN są już czytelne).
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
- **`smart_content` / obcięcie body**: `HttpException.json` parsuje tylko
  `content[:4096]`. Dla bardzo długich odpowiedzi walidacyjnych część
  komunikatów mogłaby zniknąć — akceptowalne (dotychczasowe zachowanie,
  nie pogarszamy).

## Środowisko pracy

Zgodnie z instrukcją: worktree obok repo
(`~/Programowanie/bpp-pbn-validation-error`), nowy branch od `dev`, baza DEV.
```
